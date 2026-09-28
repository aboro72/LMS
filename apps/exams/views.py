import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Count
from django.core.files.base import ContentFile
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView

from apps.accounts.mixins import RollenMixin
from apps.accounts.models import Rolle

from .forms import (
    AntwortForm,
    CSVImportForm,
    FrageForm,
    FragenkatalogForm,
    FreitextBewertungForm,
    PruefungForm,
    PruefungsThemenquoteFormSet,
    ZuordnungsPaarForm,
)
from .models import Antwort, Frage, Fragenkatalog, FragenTag, Pruefung, PruefungsAnmeldung, PruefungsbogenArchiv, PruefungsVersuch, TeilnehmerAntwort, ZuordnungsPaar
from .pdf import generiere_pruefungsbogen_pdf
from .services import NichtGenugFragenInThema, MaxVersucheErreicht, pruefe_zeitlimit, speichere_antwort, starte_pruefung, waehle_pruefungsfragen, werte_versuch_aus


def trainer_catalog_queryset(user):
    queryset = Fragenkatalog.objects.select_related("organisation", "erstellt_von")
    if not user.is_authenticated:
        return queryset.none()
    if user.is_superuser:
        return queryset
    organisation_ids = user.profile.filter(rolle=Rolle.EXAM_OPERATOR, aktiv=True).values_list("organisation_id", flat=True)
    return queryset.filter(organisation_id__in=organisation_ids)


def trainer_exam_queryset(user):
    queryset = Pruefung.objects.select_related("organisation", "fragenkatalog")
    if not user.is_authenticated:
        return queryset.none()
    if user.is_superuser:
        return queryset
    organisation_ids = user.profile.filter(rolle=Rolle.EXAM_OPERATOR, aktiv=True).values_list("organisation_id", flat=True)
    return queryset.filter(organisation_id__in=organisation_ids)


class TrainerFragenkatalogListView(RollenMixin, ListView):
    rolle = Rolle.EXAM_OPERATOR
    template_name = "exams/trainer/catalog_list.html"
    context_object_name = "kataloge"

    def get_queryset(self):
        queryset = trainer_catalog_queryset(self.request.user)
        if self.kwargs.get("org_slug"):
            queryset = queryset.filter(organisation__slug=self.kwargs["org_slug"])
        return queryset


class TrainerFragenkatalogCreateView(RollenMixin, CreateView):
    rolle = Rolle.EXAM_OPERATOR
    form_class = FragenkatalogForm
    template_name = "exams/trainer/catalog_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.erstellt_von = self.request.user
        messages.success(self.request, "Fragenkatalog wurde erstellt.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("trainer_catalog_edit", kwargs={"pk": self.object.pk})


class TrainerFragenkatalogUpdateView(RollenMixin, UpdateView):
    rolle = Rolle.EXAM_OPERATOR
    form_class = FragenkatalogForm
    template_name = "exams/trainer/catalog_form.html"

    def get_queryset(self):
        return trainer_catalog_queryset(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse("trainer_catalog_edit", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["fragen"] = self.object.fragen.prefetch_related("antworten", "zuordnungen", "tags")
        frage_form = FrageForm(fragenkatalog=self.object)
        frage_form.fields["themen"].widget.attrs["list"] = "vorhandene-themen"
        context["frage_form"] = frage_form
        context["themen"] = FragenTag.objects.filter(
            organisation=self.object.organisation,
            frage__fragenkatalog=self.object,
        ).distinct().order_by("name")
        context["antwort_form"] = AntwortForm()
        context["zuordnung_form"] = ZuordnungsPaarForm()
        context["csv_form"] = CSVImportForm()
        return context


class TrainerFragenkatalogDeleteView(RollenMixin, DeleteView):
    rolle = Rolle.EXAM_OPERATOR
    model = Fragenkatalog
    template_name = "exams/trainer/catalog_confirm_delete.html"

    def get_queryset(self):
        return trainer_catalog_queryset(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["fragen_anzahl"] = self.object.fragen.count()
        context["pruefungen_anzahl"] = Pruefung.objects.filter(fragenkatalog=self.object).count()
        return context

    def get_success_url(self):
        return reverse("trainer_catalog_list")

    def form_valid(self, form):
        titel = self.object.titel
        response = super().form_valid(form)
        messages.success(self.request, f"Fragenkatalog „{titel}“ wurde gelöscht.")
        return response


class TrainerFrageCreateView(RollenMixin, View):
    rolle = Rolle.EXAM_OPERATOR

    def get_katalog(self):
        return get_object_or_404(trainer_catalog_queryset(self.request.user), id=self.kwargs["katalog_id"])

    def get_context(self, katalog, form=None):
        form = form or FrageForm(fragenkatalog=katalog)
        form.fields["themen"].widget.attrs["list"] = "vorhandene-themen"
        return {
            "katalog": katalog,
            "form": form,
            "themen": FragenTag.objects.filter(
                organisation=katalog.organisation,
                frage__fragenkatalog=katalog,
            ).distinct().order_by("name"),
        }

    def get(self, request, *args, **kwargs):
        katalog = self.get_katalog()
        return render(request, "exams/trainer/question_create.html", self.get_context(katalog))

    def _is_correct(self, value):
        return str(value or "").strip().lower() in {"1", "true", "wahr", "richtig", "ja", "yes", "x", "on"}

    def _save_entries(self, frage, post_data):
        if frage.typ in [Frage.Typ.SINGLE_CHOICE, Frage.Typ.MULTIPLE_CHOICE, Frage.Typ.WAHR_FALSCH]:
            for index in range(1, 9):
                antworttext = post_data.get(f"antwort_{index}", "").strip()
                if antworttext:
                    Antwort.objects.create(
                        frage=frage,
                        antworttext=antworttext,
                        ist_korrekt=self._is_correct(post_data.get(f"korrekt_{index}")),
                        reihenfolge=index,
                    )
        elif frage.typ == Frage.Typ.ZUORDNUNG:
            for index in range(1, 6):
                links = post_data.get(f"links_{index}", "").strip()
                rechts = post_data.get(f"rechts_{index}", "").strip()
                if links and rechts:
                    ZuordnungsPaar.objects.create(
                        frage=frage,
                        linkes_element=links,
                        rechtes_element=rechts,
                        reihenfolge=index,
                    )

    def post(self, request, katalog_id):
        katalog = self.get_katalog()
        form = FrageForm(request.POST, fragenkatalog=katalog)
        if form.is_valid():
            frage = form.save(commit=False)
            frage.fragenkatalog = katalog
            frage.save()
            form.save_m2m()
            form.save_themen(frage)
            self._save_entries(frage, request.POST)
            messages.success(request, "Frage wurde mit Antworten erstellt.")
            if "weitere_frage" in request.POST:
                return redirect("trainer_question_create", katalog_id=katalog.pk)
            return redirect("trainer_catalog_edit", pk=katalog.pk)
        else:
            messages.error(request, "Frage konnte nicht erstellt werden.")
            return render(request, "exams/trainer/question_create.html", self.get_context(katalog, form))


class TrainerAntwortCreateView(RollenMixin, View):
    rolle = Rolle.EXAM_OPERATOR

    def post(self, request, frage_id):
        frage = get_object_or_404(Frage, id=frage_id, fragenkatalog__in=trainer_catalog_queryset(request.user))
        form_class = ZuordnungsPaarForm if frage.typ == Frage.Typ.ZUORDNUNG else AntwortForm
        form = form_class(request.POST)
        if form.is_valid():
            objekt = form.save(commit=False)
            objekt.frage = frage
            objekt.save()
            messages.success(request, "Eintrag wurde erstellt.")
        else:
            messages.error(request, "Eintrag konnte nicht erstellt werden.")
        return redirect("trainer_catalog_edit", pk=frage.fragenkatalog_id)


class TrainerCSVImportView(RollenMixin, View):
    rolle = Rolle.EXAM_OPERATOR

    def post(self, request, katalog_id):
        katalog = get_object_or_404(trainer_catalog_queryset(request.user), id=katalog_id)
        form = CSVImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    erstellt = form.importiere(katalog)
            except (ValidationError, ValueError) as exc:
                messages.error(request, f"CSV-Datei konnte nicht importiert werden: {exc}")
            else:
                messages.success(request, f"{erstellt} Fragen mit Antworten wurden importiert.")
        else:
            messages.error(request, "CSV-Datei konnte nicht importiert werden.")
        return redirect("trainer_catalog_edit", pk=katalog.pk)


class TrainerPruefungListView(RollenMixin, ListView):
    rolle = Rolle.EXAM_OPERATOR
    template_name = "exams/trainer/exam_list.html"
    context_object_name = "pruefungen"

    def get_queryset(self):
        queryset = trainer_exam_queryset(self.request.user)
        if self.kwargs.get("org_slug"):
            queryset = queryset.filter(organisation__slug=self.kwargs["org_slug"])
        return queryset


class TrainerKatalogThemenView(RollenMixin, View):
    rolle = Rolle.EXAM_OPERATOR

    def get(self, request, pk):
        katalog = get_object_or_404(trainer_catalog_queryset(request.user), pk=pk)
        themen = FragenTag.objects.filter(
            organisation=katalog.organisation,
            frage__fragenkatalog=katalog,
        ).distinct().order_by("name")
        return JsonResponse({"themen": [{"id": thema.pk, "name": thema.name} for thema in themen]})


class TrainerPruefungFormMixin:
    themen_formset_class = PruefungsThemenquoteFormSet

    def get_themen_formset(self, data=None):
        return self.themen_formset_class(
            data=data,
            instance=self.object or Pruefung(),
            form_kwargs={"pruefung": self.object},
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["themen_formset"] = kwargs.get("themen_formset") or self.get_themen_formset()
        if self.object and self.object.pk:
            context["offline_boegen"] = self.object.offline_boegen.all()[:12]
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)
        themen_formset = self.get_themen_formset(data=self.request.POST)
        if not themen_formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, themen_formset=themen_formset))
        with transaction.atomic():
            self.object.save()
            form.save_m2m()
            themen_formset.instance = self.object
            themen_formset.save()
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        return self.render_to_response(
            self.get_context_data(form=form, themen_formset=self.get_themen_formset(data=self.request.POST))
        )


class TrainerPruefungCreateView(TrainerPruefungFormMixin, RollenMixin, CreateView):
    rolle = Rolle.EXAM_OPERATOR
    form_class = PruefungForm
    template_name = "exams/trainer/exam_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        organisation = form.cleaned_data.get("organisation")
        if organisation and organisation.ist_demo_organisation:
            from apps.courses.models import Kurs
            if Pruefung.objects.filter(organisation=organisation).count() + Kurs.objects.filter(organisation=organisation).count() >= organisation.demo_inhalte_startbestand + 3:
                form.add_error(None, "In der Demo-Organisation koennen zusaetzlich hoechstens drei Kurse oder Zertifikatspruefungen angelegt werden.")
                return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(self.request, "Pruefung wurde gespeichert.")
        return reverse("trainer_exam_edit", kwargs={"pk": self.object.pk})


class TrainerPruefungUpdateView(TrainerPruefungFormMixin, RollenMixin, UpdateView):
    rolle = Rolle.EXAM_OPERATOR
    form_class = PruefungForm
    template_name = "exams/trainer/exam_form.html"

    def get_queryset(self):
        return trainer_exam_queryset(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        messages.success(self.request, "Pruefung wurde gespeichert.")
        return reverse("trainer_exam_list")


class TrainerPruefungsbogenPDFView(RollenMixin, View):
    rolle = Rolle.EXAM_OPERATOR

    def get(self, request, pk, variante):
        pruefung = get_object_or_404(trainer_exam_queryset(request.user), pk=pk)
        try:
            fragen = waehle_pruefungsfragen(pruefung)
        except NichtGenugFragenInThema as exc:
            messages.error(request, f"Prüfungsbogen konnte nicht erzeugt werden: {exc}")
            return redirect("trainer_exam_edit", pk=pruefung.pk)
        mit_loesungen = variante == "trainer"
        pdf_bytes = generiere_pruefungsbogen_pdf(pruefung, fragen, mit_loesungen=mit_loesungen)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        name = "trainer-loesungen" if mit_loesungen else "teilnehmer"
        response["Content-Disposition"] = f'attachment; filename="pruefungsbogen-{pruefung.pk}-{name}.pdf"'
        return response


class TrainerOfflinePruefungsbogenCreateView(RollenMixin, View):
    rolle = Rolle.EXAM_OPERATOR

    def post(self, request, pk):
        pruefung = get_object_or_404(trainer_exam_queryset(request.user), pk=pk)
        try:
            fragen = waehle_pruefungsfragen(pruefung)
        except NichtGenugFragenInThema as exc:
            messages.error(request, f"Offline-Pruefungsbogen konnte nicht erzeugt werden: {exc}")
            return redirect("trainer_exam_edit", pk=pruefung.pk)
        if not pruefung.zufaellige_fragenreihenfolge:
            fragen.sort(key=lambda frage: frage.id)
        archiv = PruefungsbogenArchiv.objects.create(
            pruefung=pruefung,
            erstellt_von=request.user,
            fragen_reihenfolge=[frage.pk for frage in fragen],
        )
        stamp = timezone.localtime(archiv.erstellt_am).strftime("%Y%m%d-%H%M%S")
        archiv.teilnehmer_pdf.save(
            f"pruefungsbogen-{pruefung.pk}-{stamp}-teilnehmer.pdf",
            ContentFile(generiere_pruefungsbogen_pdf(pruefung, fragen, mit_loesungen=False)),
            save=False,
        )
        archiv.loesung_pdf.save(
            f"pruefungsbogen-{pruefung.pk}-{stamp}-loesungen.pdf",
            ContentFile(generiere_pruefungsbogen_pdf(pruefung, fragen, mit_loesungen=True)),
            save=False,
        )
        archiv.save()
        messages.success(request, "Offline-Pruefungsbogen und Trainer-Lösung wurden im Archiv gespeichert.")
        return redirect("trainer_exam_edit", pk=pruefung.pk)


class TrainerOfflinePruefungsbogenDownloadView(RollenMixin, View):
    rolle = Rolle.EXAM_OPERATOR

    def get(self, request, pk, archiv_id, variante):
        pruefung = get_object_or_404(trainer_exam_queryset(request.user), pk=pk)
        archiv = get_object_or_404(PruefungsbogenArchiv, pk=archiv_id, pruefung=pruefung)
        datei = archiv.loesung_pdf if variante == "loesung" else archiv.teilnehmer_pdf
        return FileResponse(datei.open("rb"), as_attachment=True, filename=datei.name.rsplit("/", 1)[-1])


class PruefungDetailView(LoginRequiredMixin, DetailView):
    model = Pruefung
    template_name = "exams/detail.html"
    context_object_name = "pruefung"

    def get_queryset(self):
        queryset = Pruefung.objects.filter(ist_aktiv=True, organisation__aktiv=True)
        if getattr(self.request, "tenant_org", None) and not self.request.user.is_superuser:
            queryset = queryset.filter(organisation=self.request.tenant_org)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["angemeldet"] = PruefungsAnmeldung.objects.filter(nutzer=self.request.user, pruefung=self.object).exists()
        return context


class PruefungEinschreibenView(LoginRequiredMixin, View):
    def post(self, request, pk):
        queryset = Pruefung.objects.filter(pk=pk, ist_aktiv=True, organisation__aktiv=True)
        if getattr(request, "tenant_org", None) and not request.user.is_superuser:
            queryset = queryset.filter(organisation=request.tenant_org)
        pruefung = get_object_or_404(queryset)
        PruefungsAnmeldung.objects.get_or_create(nutzer=request.user, pruefung=pruefung)
        messages.success(request, "Sie sind zur Prüfung angemeldet.")
        return redirect("exam_detail", pk=pruefung.pk)


class PruefungStartView(LoginRequiredMixin, View):
    def post(self, request, pk):
        queryset = Pruefung.objects.filter(pk=pk, ist_aktiv=True, organisation__aktiv=True)
        if getattr(request, "tenant_org", None) and not request.user.is_superuser:
            queryset = queryset.filter(organisation=request.tenant_org)
        pruefung = get_object_or_404(queryset)
        if not all([request.user.first_name, request.user.last_name, request.user.geburtsdatum, request.user.geburtsort]):
            messages.error(request, "Bitte vervollständigen Sie zuerst Vorname, Nachname, Geburtsdatum und Geburtsort im Profil.")
            return redirect("profile")
        if not PruefungsAnmeldung.objects.filter(nutzer=request.user, pruefung=pruefung).exists():
            messages.error(request, "Bitte melden Sie sich zuerst zur Prüfung an.")
            return redirect("exam_detail", pk=pruefung.pk)
        try:
            versuch = starte_pruefung(pruefung, request.user)
        except MaxVersucheErreicht:
            messages.error(request, "Maximale Anzahl an Versuchen erreicht.")
            return redirect("exam_detail", pk=pruefung.pk)
        except NichtGenugFragenInThema as exc:
            messages.error(request, f"Prüfung kann nicht gestartet werden: {exc}")
            return redirect("exam_detail", pk=pruefung.pk)
        request.session[f"exam_{versuch.id}_max_index"] = 0
        messages.success(request, "Pruefung wurde gestartet.")
        return redirect("exam_take", pk=pruefung.pk, versuch_id=versuch.pk)


class PruefungAblegenView(LoginRequiredMixin, TemplateView):
    template_name = "exams/take.html"

    def dispatch(self, request, *args, **kwargs):
        queryset = Pruefung.objects.filter(pk=kwargs["pk"], ist_aktiv=True)
        if getattr(request, "tenant_org", None) and not request.user.is_superuser:
            queryset = queryset.filter(organisation=request.tenant_org)
        self.pruefung = get_object_or_404(queryset)
        self.versuch = get_object_or_404(PruefungsVersuch, pk=kwargs["versuch_id"], pruefung=self.pruefung, nutzer=request.user)
        if pruefe_zeitlimit(self.versuch):
            messages.error(request, "Das Zeitlimit wurde ueberschritten.")
            return redirect("exam_result", pk=self.pruefung.pk, versuch_id=self.versuch.pk)
        if self.versuch.status != PruefungsVersuch.Status.LAUFEND:
            return redirect("exam_result", pk=self.pruefung.pk, versuch_id=self.versuch.pk)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        index = int(request.POST.get("index", 0))
        frage = self.get_frage(index)
        if not frage:
            return redirect("exam_result", pk=self.pruefung.pk, versuch_id=self.versuch.pk)
        speichere_antwort(self.versuch, frage, request.POST)
        if "finish" in request.POST:
            werte_versuch_aus(self.versuch)
            messages.success(request, "Pruefung wurde abgegeben.")
            return redirect("exam_result", pk=self.pruefung.pk, versuch_id=self.versuch.pk)
        naechster_index = min(index + 1, len(self.versuch.fragen_reihenfolge) - 1)
        if self.pruefung.kein_zurueck:
            request.session[f"exam_{self.versuch.id}_max_index"] = max(
                request.session.get(f"exam_{self.versuch.id}_max_index", 0),
                naechster_index,
            )
        return redirect(f"{request.path}?index={naechster_index}")

    def get_frage(self, index):
        if index < 0 or index >= len(self.versuch.fragen_reihenfolge):
            return None
        return get_object_or_404(Frage.objects.prefetch_related("antworten", "zuordnungen", "teilfragen"), id=self.versuch.fragen_reihenfolge[index])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        index = int(self.request.GET.get("index", 0))
        if self.pruefung.kein_zurueck:
            index = min(index, self.request.session.get(f"exam_{self.versuch.id}_max_index", 0))
        frage = self.get_frage(index)
        bestehende_antwort = TeilnehmerAntwort.objects.filter(versuch=self.versuch, frage=frage).first() if frage else None
        antworten = list(frage.antworten.all()) if frage else []
        if self.pruefung.zufaellige_antwortfolge:
            import random

            random.shuffle(antworten)
        context.update(
            {
                "pruefung": self.pruefung,
                "versuch": self.versuch,
                "frage": frage,
                "antworten": antworten,
                "bestehende_antwort": bestehende_antwort,
                "index": index,
                "gesamt": len(self.versuch.fragen_reihenfolge),
                "is_last": index + 1 >= len(self.versuch.fragen_reihenfolge),
                "zuordnung_json": json.dumps(bestehende_antwort.zuordnung_json if bestehende_antwort else {}),
            }
        )
        return context


class PruefungErgebnisView(LoginRequiredMixin, DetailView):
    model = PruefungsVersuch
    template_name = "exams/result.html"
    context_object_name = "versuch"
    pk_url_kwarg = "versuch_id"

    def get_queryset(self):
        queryset = PruefungsVersuch.objects.filter(nutzer=self.request.user, einsehbar_bis__gte=timezone.now()).select_related("pruefung")
        if getattr(self.request, "tenant_org", None) and not self.request.user.is_superuser:
            queryset = queryset.filter(pruefung__organisation=self.request.tenant_org)
        return queryset


class PruefungErgebnisListeView(LoginRequiredMixin, ListView):
    template_name = "exams/result_list.html"
    context_object_name = "versuche"

    def get_queryset(self):
        queryset = PruefungsVersuch.objects.filter(
            nutzer=self.request.user,
            status__in=[PruefungsVersuch.Status.ABGESCHLOSSEN, PruefungsVersuch.Status.AUSSTEHEND, PruefungsVersuch.Status.ABGELAUFEN],
        ).filter(einsehbar_bis__gte=timezone.now()).select_related("pruefung")
        if getattr(self.request, "tenant_org", None) and not self.request.user.is_superuser:
            queryset = queryset.filter(pruefung__organisation=self.request.tenant_org)
        return queryset


class ExaminerQueueView(RollenMixin, ListView):
    rolle = Rolle.EXAMINER
    template_name = "exams/examiner/queue.html"
    context_object_name = "antworten"

    def get_queryset(self):
        queryset = TeilnehmerAntwort.objects.filter(
            frage__typ__in=[Frage.Typ.FREITEXT, Frage.Typ.SZENARIO],
            freitext_punkte__isnull=True,
            versuch__status=PruefungsVersuch.Status.AUSSTEHEND,
        ).select_related("versuch", "versuch__pruefung", "frage", "versuch__nutzer")
        if self.request.user.is_superuser:
            return queryset
        organisation_ids = self.request.user.profile.filter(aktiv=True).values_list("organisation_id", flat=True)
        return queryset.filter(versuch__pruefung__organisation_id__in=organisation_ids)


class ExaminerBewertungView(RollenMixin, UpdateView):
    rolle = Rolle.EXAMINER
    form_class = FreitextBewertungForm
    template_name = "exams/examiner/review.html"
    context_object_name = "antwort"

    def get_queryset(self):
        return ExaminerQueueView().get_queryset()

    def get_object(self, queryset=None):
        queryset = TeilnehmerAntwort.objects.filter(frage__typ__in=[Frage.Typ.FREITEXT, Frage.Typ.SZENARIO]).select_related("versuch", "frage", "versuch__nutzer")
        if not self.request.user.is_superuser:
            organisation_ids = self.request.user.profile.filter(aktiv=True).values_list("organisation_id", flat=True)
            queryset = queryset.filter(versuch__pruefung__organisation_id__in=organisation_ids)
        return get_object_or_404(queryset, pk=self.kwargs["pk"])

    def form_valid(self, form):
        form.instance.freitext_bewertet_von = self.request.user
        form.instance.freitext_bewertet_am = timezone.now()
        response = super().form_valid(form)
        werte_versuch_aus(self.object.versuch)
        messages.success(self.request, "Freitext wurde bewertet.")
        return response

    def get_success_url(self):
        return reverse("examiner_queue")


class TrainerPruefungStatistikView(RollenMixin, TemplateView):
    rolle = Rolle.EXAM_OPERATOR
    template_name = "exams/trainer/exam_stats.html"

    def dispatch(self, request, *args, **kwargs):
        self.pruefung = get_object_or_404(trainer_exam_queryset(request.user), pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        versuche = PruefungsVersuch.objects.filter(pruefung=self.pruefung)
        abgeschlossen = versuche.filter(status=PruefungsVersuch.Status.ABGESCHLOSSEN)
        total = versuche.count()
        bestanden = versuche.filter(bestanden=True).count()
        frage_stats = (
            TeilnehmerAntwort.objects.filter(versuch__pruefung=self.pruefung)
            .values("frage_id", "frage__typ")
            .annotate(antworten=Count("id"), punkte_avg=Avg("punkte_vergeben"))
            .order_by("frage_id")
        )
        context.update({
            "pruefung": self.pruefung,
            "versuche_count": total,
            "abgeschlossen_count": abgeschlossen.count(),
            "bestanden_count": bestanden,
            "bestehensquote": round((bestanden / total) * 100) if total else 0,
            "durchschnitt": versuche.aggregate(avg=Avg("prozent_erreicht"))["avg"] or 0,
            "frage_stats": frage_stats,
        })
        return context


class TrainerPruefungErgebnisListeView(RollenMixin, ListView):
    rolle = Rolle.EXAM_OPERATOR
    template_name = "exams/trainer/exam_results.html"
    context_object_name = "versuche"

    def dispatch(self, request, *args, **kwargs):
        self.pruefung = get_object_or_404(trainer_exam_queryset(request.user), pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return PruefungsVersuch.objects.filter(pruefung=self.pruefung).select_related("nutzer").order_by("-gestartet_am")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pruefung"] = self.pruefung
        return context
