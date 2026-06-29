from django.urls import path

from .views import (
    EinschreibenView,
    KursBewertungCreateView,
    KursDetailView,
    KursKatalogView,
    KursLernenView,
    LernpfadDetailView,
    LernpfadEinschreibenView,
    LernpfadListView,
    LektionAbschliessenView,
    LektionDetailView,
    LektionUebungPruefenView,
    TrainerAbschnittCreateView,
    TrainerKursCreateView,
    TrainerKursListView,
    TrainerKursUpdateView,
    TrainerUmsatzDashboardView,
    TrainerLektionCreateView,
    TrainerMaterialCreateView,
    TrainerUebungsantwortCreateView,
    TrainerUebungsfrageCreateView,
)


urlpatterns = [
    path("kurse/", KursKatalogView.as_view(), name="course_catalog"),
    path("kurse/<slug:slug>/", KursDetailView.as_view(), name="course_detail"),
    path("kurse/<slug:slug>/einschreiben/", EinschreibenView.as_view(), name="course_enroll"),
    path("kurse/<slug:slug>/bewerten/", KursBewertungCreateView.as_view(), name="course_review"),
    path("kurse/<slug:slug>/lernen/", KursLernenView.as_view(), name="course_learn"),
    path("kurse/<slug:slug>/lernen/<int:lektion_id>/", LektionDetailView.as_view(), name="course_lesson"),
    path(
        "kurse/<slug:slug>/lernen/<int:lektion_id>/abschliessen/",
        LektionAbschliessenView.as_view(),
        name="course_lesson_complete",
    ),
    path(
        "kurse/<slug:slug>/lernen/<int:lektion_id>/uebung/",
        LektionUebungPruefenView.as_view(),
        name="course_lesson_exercise",
    ),
    path("lernpfade/", LernpfadListView.as_view(), name="learning_path_list"),
    path("lernpfade/<slug:slug>/", LernpfadDetailView.as_view(), name="learning_path_detail"),
    path("lernpfade/<slug:slug>/einschreiben/", LernpfadEinschreibenView.as_view(), name="learning_path_enroll"),
    path("trainer/umsatz/", TrainerUmsatzDashboardView.as_view(), name="trainer_revenue_dashboard"),
    path("trainer/kurse/", TrainerKursListView.as_view(), name="trainer_course_list"),
    path("trainer/kurse/neu/", TrainerKursCreateView.as_view(), name="trainer_course_create"),
    path("trainer/kurse/<slug:slug>/", TrainerKursUpdateView.as_view(), name="trainer_course_edit"),
    path(
        "trainer/kurse/<slug:slug>/abschnitte/neu/",
        TrainerAbschnittCreateView.as_view(),
        name="trainer_section_create",
    ),
    path(
        "trainer/kurse/<slug:slug>/abschnitte/<int:abschnitt_id>/lektionen/neu/",
        TrainerLektionCreateView.as_view(),
        name="trainer_lesson_create",
    ),
    path(
        "trainer/kurse/<slug:slug>/lektionen/<int:lektion_id>/material/neu/",
        TrainerMaterialCreateView.as_view(),
        name="trainer_material_create",
    ),
    path(
        "trainer/kurse/<slug:slug>/lektionen/<int:lektion_id>/uebungsfragen/neu/",
        TrainerUebungsfrageCreateView.as_view(),
        name="trainer_exercise_question_create",
    ),
    path(
        "trainer/kurse/<slug:slug>/uebungsfragen/<int:frage_id>/antworten/neu/",
        TrainerUebungsantwortCreateView.as_view(),
        name="trainer_exercise_answer_create",
    ),
]
