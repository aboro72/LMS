from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView

from .forms import RegisterForm


class HomeView(TemplateView):
    template_name = "home.html"


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["profile"] = self.request.user.profile.select_related("organisation").filter(aktiv=True)
        context["einschreibungen"] = (
            self.request.user.einschreibung_set.select_related("kurs", "kurs__organisation")
            .order_by("-eingeschrieben_am")
            if self.request.user.is_authenticated
            else []
        )
        return context


class RegisterView(CreateView):
    form_class = RegisterForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("account_login")
