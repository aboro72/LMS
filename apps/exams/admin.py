from django.contrib import admin

from .models import Antwort, Frage, Fragenkatalog, FragenTag, Pruefung, PruefungsThemenquote, PruefungsVersuch, TeilnehmerAntwort, ZuordnungsPaar


class AntwortInline(admin.TabularInline):
    model = Antwort
    extra = 2


class ZuordnungsPaarInline(admin.TabularInline):
    model = ZuordnungsPaar
    extra = 2


class PruefungsThemenquoteInline(admin.TabularInline):
    model = PruefungsThemenquote
    extra = 1


@admin.register(Fragenkatalog)
class FragenkatalogAdmin(admin.ModelAdmin):
    list_display = ("titel", "organisation", "erstellt_von", "erstellt_am")
    list_filter = ("organisation",)
    search_fields = ("titel", "beschreibung", "organisation__name")
    autocomplete_fields = ("organisation", "erstellt_von")


@admin.register(FragenTag)
class FragenTagAdmin(admin.ModelAdmin):
    list_display = ("name", "organisation")
    list_filter = ("organisation",)
    search_fields = ("name",)


@admin.register(Frage)
class FrageAdmin(admin.ModelAdmin):
    list_display = ("id", "fragenkatalog", "typ", "schwierigkeit", "punkte")
    list_filter = ("typ", "schwierigkeit", "fragenkatalog__organisation")
    search_fields = ("fragetext", "fragenkatalog__titel")
    inlines = (AntwortInline, ZuordnungsPaarInline)


@admin.register(Antwort)
class AntwortAdmin(admin.ModelAdmin):
    list_display = ("frage", "antworttext", "ist_korrekt", "reihenfolge")
    list_filter = ("ist_korrekt", "frage__typ")
    search_fields = ("antworttext",)


@admin.register(ZuordnungsPaar)
class ZuordnungsPaarAdmin(admin.ModelAdmin):
    list_display = ("frage", "linkes_element", "rechtes_element", "reihenfolge")
    search_fields = ("linkes_element", "rechtes_element")


@admin.register(Pruefung)
class PruefungAdmin(admin.ModelAdmin):
    list_display = ("titel", "organisation", "fragenkatalog", "anzahl_fragen", "ist_aktiv")
    list_filter = ("ist_aktiv", "organisation")
    search_fields = ("titel", "beschreibung", "fragenkatalog__titel")
    inlines = (PruefungsThemenquoteInline,)


@admin.register(PruefungsVersuch)
class PruefungsVersuchAdmin(admin.ModelAdmin):
    list_display = ("nutzer", "pruefung", "versuch_nummer", "status", "prozent_erreicht", "bestanden")
    list_filter = ("status", "bestanden", "pruefung__organisation")
    search_fields = ("nutzer__username", "pruefung__titel")


@admin.register(TeilnehmerAntwort)
class TeilnehmerAntwortAdmin(admin.ModelAdmin):
    list_display = ("versuch", "frage", "ist_korrekt", "punkte_vergeben")
    list_filter = ("ist_korrekt", "frage__typ")
    search_fields = ("versuch__nutzer__username",)
