from django.urls import path

from .views import InstallationView

urlpatterns = [path("", InstallationView.as_view(), name="installer_setup")]
