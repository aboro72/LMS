from django.contrib import admin

from .models import Einladung, Organisation


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "lizenz_typ", "max_nutzer", "max_kurse", "aktiv", "erstellt_am")
    list_filter = ("lizenz_typ", "aktiv")
    search_fields = ("name", "slug", "kontakt_email")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Einladung)
class EinladungAdmin(admin.ModelAdmin):
    list_display = ("email", "organisation", "rolle", "erstellt_am", "akzeptiert_am", "abgelaufen_am")
    list_filter = ("rolle", "organisation", "akzeptiert_am")
    search_fields = ("email", "organisation__name")
    readonly_fields = ("token", "erstellt_am")
