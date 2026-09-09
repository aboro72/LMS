from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Count, Prefetch, Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from apps.accounts.mixins import RollenMixin
from apps.accounts.models import Rolle

from .forms import (
    AbschnittForm,
    BegleitmaterialForm,
    KursBewertungForm,
    KursForm,
    LektionForm,
    UebungsantwortForm,
    UebungsfrageForm,
)
from .models import (
    Abschnitt,
    Begleitmaterial,
    Einschreibung,
    Kurs,
    KursBewertung,
    Lektion,
    Lernpfad,
    LernpfadEinschreibung,
    LektionsFortschritt,
    Uebungsantwort,
    Uebungsfrage,
)

def trainer_course_queryset(user):
    queryset = Kurs.objects.select_related("organisation", "erstellt_von")
    if not user.is_authenticated:
        return queryset.none()
    if user.is_superuser:
        return queryset
    organisation_ids = user.profile.filter(rolle=Rolle.TRAINER, aktiv=True).values_list("organisation_id", flat=True)
    return queryset.filter(organisation_id__in=organisation_ids)


def kurszugriff_bezahlt(user, kurs):
    if kurs.ist_kostenlos or kurs.preis <= 0:
        return True
    if not user.is_authenticated:
        return False
    return Einschreibung.objects.filter(nutzer=user, kurs=kurs, bezahlt=True).exists()


class DashboardCourseMixin(LoginRequiredMixin):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["einschreibungen"] = (
            Einschreibung.objects.filter(nutzer=self.request.user)
            .select_related("kurs", "kurs__organisation")
            .order_by("-eingeschrieben_am")
        )
        return context


class KursKatalogView(ListView):
    model = Kurs
    template_name = "courses/catalog.html"
    context_object_name = "kurse"
    paginate_by = 12

    def get_queryset(self):
        queryset = (
            Kurs.objects.filter(ist_veroeffentlicht=True, organisation__aktiv=True)
            .select_related("organisation", "erstellt_von")
            .prefetch_related("abschnitte__lektionen", "bewertungen")
        )
        query = self.request.GET.get("q", "").strip()
        niveau = self.request.GET.get("niveau", "").strip()
        sprache = self.request.GET.get("sprache", "").strip()
        preis = self.request.GET.get("preis", "").strip()
        if query:
            queryset = queryset.filter(Q(titel__icontains=query) | Q(beschreibung__icontains=query))
        if niveau:
            queryset = queryset.filter(niveau=niveau)
        if sprache:
            queryset = queryset.filter(sprache=sprache)
        if preis == "kostenlos":
            queryset = queryset.filter(ist_kostenlos=True)
        elif preis == "bezahlt":
            queryset = queryset.filter(ist_kostenlos=False)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter"] = self.request.GET
        context["niveau_choices"] = Kurs._meta.get_field("niveau").choices
        return context


class KursDetailView(DetailView):
    model = Kurs
    template_name = "courses/detail.html"
    context_object_name = "kurs"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return (
            Kurs.objects.filter(ist_veroeffentlicht=True, organisation__aktiv=True)
            .select_related("organisation", "erstellt_von")
            .prefetch_related("abschnitte__lektionen", "bewertungen")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.payments.models import Zahlungseinstellungen
        context["payment_aktiv"] = Zahlungseinstellungen.load().payment_aktiv
        if self.request.user.is_authenticated:
            context["einschreibung"] = Einschreibung.objects.filter(
                nutzer=self.request.user,
                kurs=self.object,
                bezahlt=True,
            ).first()
        return context


class EinschreibenView(LoginRequiredMixin, View):
    def post(self, request, slug):
        kurs = get_object_or_404(Kurs, slug=slug, ist_veroeffentlicht=True, organisation__aktiv=True)
        if not kurs.ist_kostenlos and kurs.preis > 0:
            return redirect("course_checkout", slug=kurs.slug)
        Einschreibung.objects.update_or_create(nutzer=request.user, kurs=kurs, defaults={"bezahlt": True})
        messages.success(request, "Du bist in den Kurs eingeschrieben.")
        return redirect("course_learn", slug=kurs.slug)


class KursLernenView(LoginRequiredMixin, DetailView):
    model = Kurs
    template_name = "courses/learn.html"
    context_object_name = "kurs"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return Kurs.objects.filter(ist_veroeffentlicht=True).prefetch_related(
            Prefetch(
                "abschnitte",
                queryset=Abschnitt.objects.prefetch_related(
                    "lektionen__materialien",
                    "lektionen__uebungsfragen__antworten",
                ),
            )
        )

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not kurszugriff_bezahlt(request.user, self.object):
            messages.warning(request, "Bitte bezahle den Kurs, um unbegrenzten Zugriff zu erhalten.")
            return redirect("course_checkout", slug=self.object.slug)
        self.einschreibung, _ = Einschreibung.objects.update_or_create(
            nutzer=request.user,
            kurs=self.object,
            defaults={"bezahlt": True},
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        erste_lektion = Lektion.objects.filter(abschnitt__kurs=self.object).order_by(
            "abschnitt__reihenfolge",
            "reihenfolge",
        ).first()
        context["lektion"] = erste_lektion
        context.update(self._learning_context(erste_lektion))
        return context

    def _learning_context(self, lektion):
        abgeschlossene_ids = set(
            LektionsFortschritt.objects.filter(einschreibung=self.einschreibung).values_list(
                "lektion_id",
                flat=True,
            )
        )
        return {
            "einschreibung": self.einschreibung,
            "abgeschlossene_ids": abgeschlossene_ids,
            "vorherige_lektion": None,
            "naechste_lektion": self._naechste_lektion(lektion),
            "uebung_ergebnis": self.request.session.pop(f"lesson_exercise_{lektion.id}", None) if lektion else None,
        }

    def _naechste_lektion(self, lektion):
        if not lektion:
            return None
        lektionen = list(
            Lektion.objects.filter(abschnitt__kurs=self.object).order_by("abschnitt__reihenfolge", "reihenfolge")
        )
        try:
            index = lektionen.index(lektion)
        except ValueError:
            return None
        return lektionen[index + 1] if index + 1 < len(lektionen) else None


class LektionDetailView(KursLernenView):
    def get_context_data(self, **kwargs):
        context = {"kurs": self.object, "object": self.object}
        lektion = get_object_or_404(Lektion, id=self.kwargs["lektion_id"], abschnitt__kurs=self.object)
        lektionen = list(
            Lektion.objects.filter(abschnitt__kurs=self.object).order_by("abschnitt__reihenfolge", "reihenfolge")
        )
        index = lektionen.index(lektion)
        context["lektion"] = lektion
        context.update(
            {
                **self._learning_context(lektion),
                "vorherige_lektion": lektionen[index - 1] if index > 0 else None,
                "naechste_lektion": lektionen[index + 1] if index + 1 < len(lektionen) else None,
            }
        )
        return context


class LektionAbschliessenView(LoginRequiredMixin, View):
    def post(self, request, slug, lektion_id):
        kurs = get_object_or_404(Kurs, slug=slug, ist_veroeffentlicht=True)
        if not kurszugriff_bezahlt(request.user, kurs):
            return redirect("course_checkout", slug=kurs.slug)
        einschreibung, _ = Einschreibung.objects.get_or_create(nutzer=request.user, kurs=kurs)
        lektion = get_object_or_404(Lektion, id=lektion_id, abschnitt__kurs=kurs)
        LektionsFortschritt.objects.get_or_create(einschreibung=einschreibung, lektion=lektion)
        einschreibung.aktualisiere_fortschritt()
        messages.success(request, "Lektion wurde als abgeschlossen markiert.")
        return redirect("course_lesson", slug=kurs.slug, lektion_id=lektion.id)


class LektionUebungPruefenView(LoginRequiredMixin, View):
    def post(self, request, slug, lektion_id):
        kurs = get_object_or_404(Kurs, slug=slug, ist_veroeffentlicht=True)
        get_object_or_404(Einschreibung, nutzer=request.user, kurs=kurs, bezahlt=True)
        lektion = get_object_or_404(Lektion, id=lektion_id, abschnitt__kurs=kurs)
        fragen = list(lektion.uebungsfragen.filter(aktiv=True).prefetch_related("antworten"))
        richtig = 0
        details = []
        for frage in fragen:
            ausgewaehlt = set(request.POST.getlist(f"uebungsfrage_{frage.id}"))
            korrekt = {str(antwort.id) for antwort in frage.antworten.filter(ist_korrekt=True)}
            ist_richtig = ausgewaehlt == korrekt
            if ist_richtig:
                richtig += 1
            details.append(
                {
                    "frage": frage.frage,
                    "ist_richtig": ist_richtig,
                    "erklaerung": frage.erklaerung,
                }
            )
        request.session[f"lesson_exercise_{lektion.id}"] = {
            "richtig": richtig,
            "gesamt": len(fragen),
            "details": details,
        }
        return redirect("course_lesson", slug=kurs.slug, lektion_id=lektion.id)


class TrainerKursListView(RollenMixin, ListView):
    rolle = Rolle.TRAINER
    model = Kurs
    template_name = "courses/trainer/course_list.html"
    context_object_name = "kurse"

    def get_queryset(self):
        return trainer_course_queryset(self.request.user)


class TrainerKursCreateView(RollenMixin, CreateView):
    rolle = Rolle.TRAINER
    model = Kurs
    form_class = KursForm
    template_name = "courses/trainer/course_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        org = form.cleaned_data.get("organisation")
        if org and org.max_kurse and org.max_kurse > 0:
            if Kurs.objects.filter(organisation=org).count() >= org.max_kurse:
                messages.error(
                    self.request,
                    f"Kurslimit ({org.max_kurse}) dieser Organisation erreicht. "
                    "Bitte upgraden Sie die Lizenz.",
                )
                return self.form_invalid(form)
        form.instance.erstellt_von = self.request.user
        messages.success(self.request, "Kurs wurde erstellt.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("trainer_course_edit", kwargs={"slug": self.object.slug})


class TrainerKursUpdateView(RollenMixin, UpdateView):
    rolle = Rolle.TRAINER
    model = Kurs
    form_class = KursForm
    template_name = "courses/trainer/course_form.html"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return trainer_course_queryset(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Kurs wurde gespeichert.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("trainer_course_edit", kwargs={"slug": self.object.slug})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["abschnitt_form"] = AbschnittForm()
        context["lektion_form"] = LektionForm()
        context["material_form"] = BegleitmaterialForm()
        context["uebungsfrage_form"] = UebungsfrageForm()
        context["uebungsantwort_form"] = UebungsantwortForm()
        context["abschnitte"] = self.object.abschnitte.prefetch_related(
            "lektionen__materialien",
            "lektionen__uebungsfragen__antworten",
        )
        return context


class TrainerAbschnittCreateView(RollenMixin, View):
    rolle = Rolle.TRAINER

    def post(self, request, slug):
        kurs = get_object_or_404(trainer_course_queryset(request.user), slug=slug)
        form = AbschnittForm(request.POST)
        if form.is_valid():
            abschnitt = form.save(commit=False)
            abschnitt.kurs = kurs
            abschnitt.save()
            messages.success(request, "Abschnitt wurde erstellt.")
        else:
            messages.error(request, "Abschnitt konnte nicht erstellt werden.")
        return redirect("trainer_course_edit", slug=kurs.slug)


class TrainerLektionCreateView(RollenMixin, View):
    rolle = Rolle.TRAINER

    def post(self, request, slug, abschnitt_id):
        kurs = get_object_or_404(trainer_course_queryset(request.user), slug=slug)
        abschnitt = get_object_or_404(Abschnitt, id=abschnitt_id, kurs=kurs)
        form = LektionForm(request.POST, request.FILES)
        if form.is_valid():
            lektion = form.save(commit=False)
            lektion.abschnitt = abschnitt
            lektion.save()
            messages.success(request, "Lektion wurde erstellt.")
        else:
            messages.error(request, "Lektion konnte nicht erstellt werden.")
        return redirect("trainer_course_edit", slug=kurs.slug)


class TrainerMaterialCreateView(RollenMixin, View):
    rolle = Rolle.TRAINER

    def post(self, request, slug, lektion_id):
        kurs = get_object_or_404(trainer_course_queryset(request.user), slug=slug)
        lektion = get_object_or_404(Lektion, id=lektion_id, abschnitt__kurs=kurs)
        form = BegleitmaterialForm(request.POST, request.FILES)
        if form.is_valid():
            material = form.save(commit=False)
            material.lektion = lektion
            material.save()
            messages.success(request, "Begleitmaterial wurde hochgeladen.")
        else:
            messages.error(request, "Begleitmaterial konnte nicht gespeichert werden.")
        return redirect("trainer_course_edit", slug=kurs.slug)


class TrainerUebungsfrageCreateView(RollenMixin, View):
    rolle = Rolle.TRAINER

    def post(self, request, slug, lektion_id):
        kurs = get_object_or_404(trainer_course_queryset(request.user), slug=slug)
        lektion = get_object_or_404(Lektion, id=lektion_id, abschnitt__kurs=kurs)
        form = UebungsfrageForm(request.POST)
        if form.is_valid():
            frage = form.save(commit=False)
            frage.lektion = lektion
            frage.save()
            messages.success(request, "Uebungsfrage wurde erstellt.")
        else:
            messages.error(request, "Uebungsfrage konnte nicht gespeichert werden.")
        return redirect("trainer_course_edit", slug=kurs.slug)


class TrainerUebungsantwortCreateView(RollenMixin, View):
    rolle = Rolle.TRAINER

    def post(self, request, slug, frage_id):
        kurs = get_object_or_404(trainer_course_queryset(request.user), slug=slug)
        frage = get_object_or_404(Uebungsfrage, id=frage_id, lektion__abschnitt__kurs=kurs)
        form = UebungsantwortForm(request.POST)
        if form.is_valid():
            antwort = form.save(commit=False)
            antwort.frage = frage
            antwort.save()
            messages.success(request, "Uebungsantwort wurde erstellt.")
        else:
            messages.error(request, "Uebungsantwort konnte nicht gespeichert werden.")
        return redirect("trainer_course_edit", slug=kurs.slug)


class KursBewertungCreateView(LoginRequiredMixin, View):
    def post(self, request, slug):
        kurs = get_object_or_404(Kurs, slug=slug, ist_veroeffentlicht=True, organisation__aktiv=True)
        if not Einschreibung.objects.filter(nutzer=request.user, kurs=kurs, bezahlt=True).exists():
            messages.error(request, "Nur eingeschriebene Nutzer koennen diesen Kurs bewerten.")
            return redirect("course_detail", slug=kurs.slug)
        form = KursBewertungForm(request.POST)
        if form.is_valid():
            KursBewertung.objects.update_or_create(
                kurs=kurs,
                nutzer=request.user,
                defaults=form.cleaned_data,
            )
            messages.success(request, "Bewertung wurde gespeichert.")
        else:
            messages.error(request, "Bewertung konnte nicht gespeichert werden.")
        return redirect("course_detail", slug=kurs.slug)


class LernpfadListView(ListView):
    model = Lernpfad
    template_name = "courses/learning_path_list.html"
    context_object_name = "lernpfade"
    paginate_by = 12

    def get_queryset(self):
        return Lernpfad.objects.filter(
            ist_veroeffentlicht=True,
            organisation__aktiv=True,
        ).select_related("organisation").prefetch_related("pfad_kurse__kurs")


class LernpfadDetailView(DetailView):
    model = Lernpfad
    template_name = "courses/learning_path_detail.html"
    context_object_name = "lernpfad"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return Lernpfad.objects.filter(
            ist_veroeffentlicht=True,
            organisation__aktiv=True,
        ).select_related("organisation").prefetch_related("pfad_kurse__kurs")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        einschreibung = None
        if self.request.user.is_authenticated:
            einschreibung = LernpfadEinschreibung.objects.filter(
                nutzer=self.request.user,
                lernpfad=self.object,
            ).first()
        context["einschreibung"] = einschreibung
        return context


class LernpfadEinschreibenView(LoginRequiredMixin, View):
    def post(self, request, slug):
        lernpfad = get_object_or_404(Lernpfad, slug=slug, ist_veroeffentlicht=True, organisation__aktiv=True)
        LernpfadEinschreibung.objects.get_or_create(nutzer=request.user, lernpfad=lernpfad)
        for pfad_kurs in lernpfad.pfad_kurse.select_related("kurs"):
            if pfad_kurs.kurs.ist_kostenlos or pfad_kurs.kurs.preis <= 0:
                Einschreibung.objects.update_or_create(
                    nutzer=request.user,
                    kurs=pfad_kurs.kurs,
                    defaults={"bezahlt": True},
                )
        messages.success(request, "Du bist in den Lernpfad eingeschrieben.")
        return redirect("learning_path_detail", slug=lernpfad.slug)


class TrainerUmsatzDashboardView(RollenMixin, TemplateView):
    rolle = Rolle.TRAINER
    template_name = "courses/trainer/revenue_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.payments.models import Zahlung, Zahlungsstatus

        zahlungen = Zahlung.objects.filter(trainer=self.request.user, status=Zahlungsstatus.BEZAHLT)
        context["summe_brutto"] = zahlungen.aggregate(total=Sum("betrag_brutto"))["total"] or 0
        context["summe_trainer"] = zahlungen.aggregate(total=Sum("trainer_anteil"))["total"] or 0
        context["zahlungen_count"] = zahlungen.count()
        context["kurs_summen"] = (
            zahlungen.values("kurs__titel")
            .annotate(brutto=Sum("betrag_brutto"), trainer=Sum("trainer_anteil"), anzahl=Count("id"))
            .order_by("-trainer")
        )
        context["letzte_zahlungen"] = zahlungen.select_related("kurs", "nutzer").order_by("-bezahlt_am")[:10]
        return context
