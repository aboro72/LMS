import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView

from apps.accounts.mixins import RollenMixin
from apps.accounts.models import Rolle

from .forms import AntwortForm, CSVImportForm, FrageForm, FragenkatalogForm, FreitextBewertungForm, PruefungForm, ZuordnungsPaarForm
from .models import Antwort, Frage, Fragenkatalog, Pruefung, PruefungsVersuch, TeilnehmerAntwort, ZuordnungsPaar
from .services import MaxVersucheErreicht, pruefe_zeitlimit, speichere_antwort, starte_pruefung, werte_versuch_aus


def trainer_catalog_queryset(user):
    queryset = Fragenkatalog.objects.select_related("organisation", "erstellt_von")
    if not user.is_authenticated:
        return queryset.none()
    if user.is_superuser:
        return queryset
    organisation_ids = user.profile.filter(aktiv=True).values_list("organisation_id", flat=True)
    return queryset.filter(organisation_id__in=organisation_ids)


def trainer_exam_queryset(user):
    queryset = Pruefung.objects.select_related("organisation", "fragenkatalog")
    if not user.is_authenticated:
        return queryset.none()
    if user.is_superuser:
        return queryset
    organisation_ids = user.profile.filter(aktiv=True).values_list("organisation_id", flat=True)
    return queryset.filter(organisation_id__in=organisation_ids)


class TrainerFragenkatalogListView(RollenMixin, ListView):
    rolle = Rolle.TRAINER
    template_name = "exams/trainer/catalog_list.html"
    context_object_name = "kataloge"

    def get_queryset(self):
        return trainer_catalog_queryset(self.request.user)


class TrainerFragenkatalogCreateView(RollenMixin, CreateView):
    rolle = Rolle.TRAINER
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
    rolle = Rolle.TRAINER
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
        context["fragen"] = self.object.fragen.prefetch_related("antworten", "zuordnungen")
        context["frage_form"] = FrageForm(fragenkatalog=self.object)
        context["antwort_form"] = AntwortForm()
        context["zuordnung_form"] = ZuordnungsPaarForm()
        context["csv_form"] = CSVImportForm()
        return context


class TrainerFrageCreateView(RollenMixin, View):
    rolle = Rolle.TRAINER

    def post(self, request, katalog_id):
        katalog = get_object_or_404(trainer_catalog_queryset(request.user), id=katalog_id)
        form = FrageForm(request.POST, fragenkatalog=katalog)
        if form.is_valid():
            frage = form.save(commit=False)
            frage.fragenkatalog = katalog
            frage.save()
            form.save_m2m()
            messages.success(request, "Frage wurde erstellt.")
        else:
            messages.error(request, "Frage konnte nicht erstellt werden.")
        return redirect("trainer_catalog_edit", pk=katalog.pk)


class TrainerAntwortCreateView(RollenMixin, View):
    rolle = Rolle.TRAINER

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
    rolle = Rolle.TRAINER

    def post(self, request, katalog_id):
        katalog = get_object_or_404(trainer_catalog_queryset(request.user), id=katalog_id)
        form = CSVImportForm(request.POST, request.FILES)
        if form.is_valid():
            erstellt = form.importiere(katalog)
            messages.success(request, f"{erstellt} Fragen wurden importiert.")
        else:
            messages.error(request, "CSV-Datei konnte nicht importiert werden.")
        return redirect("trainer_catalog_edit", pk=katalog.pk)


class TrainerPruefungListView(RollenMixin, ListView):
    rolle = Rolle.TRAINER
    template_name = "exams/trainer/exam_list.html"
    context_object_name = "pruefungen"

    def get_queryset(self):
        return trainer_exam_queryset(self.request.user)


class TrainerPruefungCreateView(RollenMixin, CreateView):
    rolle = Rolle.TRAINER
    form_class = PruefungForm
    template_name = "exams/trainer/exam_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        messages.success(self.request, "Pruefung wurde gespeichert.")
        return reverse("trainer_exam_list")


class TrainerPruefungUpdateView(RollenMixin, UpdateView):
    rolle = Rolle.TRAINER
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


class PruefungDetailView(LoginRequiredMixin, DetailView):
    model = Pruefung
    template_name = "exams/detail.html"
    context_object_name = "pruefung"

    def get_queryset(self):
        return Pruefung.objects.filter(ist_aktiv=True, organisation__aktiv=True)


class PruefungStartView(LoginRequiredMixin, View):
    def post(self, request, pk):
        pruefung = get_object_or_404(Pruefung, pk=pk, ist_aktiv=True, organisation__aktiv=True)
        try:
            versuch = starte_pruefung(pruefung, request.user)
        except MaxVersucheErreicht:
            messages.error(request, "Maximale Anzahl an Versuchen erreicht.")
            return redirect("exam_detail", pk=pruefung.pk)
        request.session[f"exam_{versuch.id}_max_index"] = 0
        messages.success(request, "Pruefung wurde gestartet.")
        return redirect("exam_take", pk=pruefung.pk, versuch_id=versuch.pk)


class PruefungAblegenView(LoginRequiredMixin, TemplateView):
    template_name = "exams/take.html"

    def dispatch(self, request, *args, **kwargs):
        self.pruefung = get_object_or_404(Pruefung, pk=kwargs["pk"], ist_aktiv=True)
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
        return PruefungsVersuch.objects.filter(nutzer=self.request.user).select_related("pruefung")


class ExaminerQueueView(RollenMixin, ListView):
    rolle = Rolle.EXAMINER
    template_name = "exams/examiner/queue.html"
    context_object_name = "antworten"

    def get_queryset(self):
        queryset = TeilnehmerAntwort.objects.filter(
            frage__typ=Frage.Typ.FREITEXT,
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
        queryset = TeilnehmerAntwort.objects.filter(frage__typ=Frage.Typ.FREITEXT).select_related("versuch", "frage", "versuch__nutzer")
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
