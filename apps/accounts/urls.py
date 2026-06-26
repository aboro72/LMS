from django.urls import path

from .views import DashboardView, RegisterView


urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
]
