from django.contrib import admin

from .models import (
    Abschnitt,
    Begleitmaterial,
    Einschreibung,
    Kurs,
    Lektion,
    LektionsFortschritt,
    Uebungsantwort,
    Uebungsfrage,
)


class LektionInline(admin.TabularInline):
    model = Lektion
    extra = 1
    fields = ("titel", "typ", "reihenfolge", "dauer_minuten", "ist_vorschau")


class BegleitmaterialInline(admin.TabularInline):
    model = Begleitmaterial
    extra = 1
    fields = ("titel", "datei", "reihenfolge")


class UebungsantwortInline(admin.TabularInline):
    model = Uebungsantwort
    extra = 2
    fields = ("antwort", "ist_korrekt", "reihenfolge")


class AbschnittInline(admin.TabularInline):
    model = Abschnitt
    extra = 1
    fields = ("titel", "reihenfolge", "ist_veroeffentlicht")


@admin.register(Kurs)
class KursAdmin(admin.ModelAdmin):
    list_display = ("titel", "organisation", "niveau", "sprache", "ist_veroeffentlicht", "erstellt_von")
    list_filter = ("niveau", "sprache", "ist_veroeffentlicht", "organisation")
    search_fields = ("titel", "organisation__name", "erstellt_von__username")
    prepopulated_fields = {"slug": ("titel",)}
    autocomplete_fields = ("organisation", "erstellt_von")
    inlines = (AbschnittInline,)


@admin.register(Abschnitt)
class AbschnittAdmin(admin.ModelAdmin):
    list_display = ("titel", "kurs", "reihenfolge", "ist_veroeffentlicht")
    list_filter = ("ist_veroeffentlicht", "kurs__organisation")
    search_fields = ("titel", "kurs__titel")
    inlines = (LektionInline,)


@admin.register(Lektion)
class LektionAdmin(admin.ModelAdmin):
    list_display = ("titel", "abschnitt", "typ", "reihenfolge", "dauer_minuten", "ist_vorschau")
    list_filter = ("typ", "ist_vorschau", "abschnitt__kurs__organisation")
    search_fields = ("titel", "abschnitt__titel", "abschnitt__kurs__titel")
    inlines = (BegleitmaterialInline,)


@admin.register(Begleitmaterial)
class BegleitmaterialAdmin(admin.ModelAdmin):
    list_display = ("titel", "lektion", "reihenfolge", "erstellt_am")
    search_fields = ("titel", "lektion__titel", "lektion__abschnitt__kurs__titel")


@admin.register(Uebungsfrage)
class UebungsfrageAdmin(admin.ModelAdmin):
    list_display = ("frage", "lektion", "reihenfolge", "aktiv")
    list_filter = ("aktiv", "lektion__abschnitt__kurs__organisation")
    search_fields = ("frage", "lektion__titel")
    inlines = (UebungsantwortInline,)


@admin.register(Uebungsantwort)
class UebungsantwortAdmin(admin.ModelAdmin):
    list_display = ("antwort", "frage", "ist_korrekt", "reihenfolge")
    list_filter = ("ist_korrekt",)
    search_fields = ("antwort", "frage__frage")


@admin.register(Einschreibung)
class EinschreibungAdmin(admin.ModelAdmin):
    list_display = ("nutzer", "kurs", "fortschritt_prozent", "bezahlt", "eingeschrieben_am")
    list_filter = ("bezahlt", "kurs__organisation")
    search_fields = ("nutzer__username", "nutzer__email", "kurs__titel")


@admin.register(LektionsFortschritt)
class LektionsFortschrittAdmin(admin.ModelAdmin):
    list_display = ("einschreibung", "lektion", "abgeschlossen_am")
    search_fields = ("einschreibung__nutzer__username", "lektion__titel")
