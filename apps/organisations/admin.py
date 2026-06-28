from django.contrib import admin

from .models import (
    Einladung,
    Organisation,
    OrganisationDesign,
    OrganisationEmailKonfiguration,
    OrganisationStartseite,
)


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


@admin.register(OrganisationEmailKonfiguration)
class OrganisationEmailKonfigAdmin(admin.ModelAdmin):
    list_display = ("organisation", "absender_email", "smtp_host", "smtp_port", "aktiv")
    list_filter = ("aktiv", "smtp_use_tls", "smtp_use_ssl")
    search_fields = ("organisation__name", "absender_email", "smtp_host")


@admin.register(OrganisationDesign)
class OrganisationDesignAdmin(admin.ModelAdmin):
    list_display = ("organisation", "primary_color", "secondary_color", "navbar_farbe")
    search_fields = ("organisation__name",)


@admin.register(OrganisationStartseite)
class OrganisationStartseiteAdmin(admin.ModelAdmin):
    list_display = ("organisation", "hero_titel", "aktiv")
    list_filter = ("aktiv",)
    search_fields = ("organisation__name", "hero_titel")
