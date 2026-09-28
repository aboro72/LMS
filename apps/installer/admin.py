from django.contrib import admin

from .models import InstallationState


@admin.register(InstallationState)
class InstallationStateAdmin(admin.ModelAdmin):
    list_display = ("completed_at",)
