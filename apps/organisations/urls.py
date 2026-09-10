from django.urls import path

from .views import (
    OffentlicheStartseiteRedirectView,
    OffentlicheStartseiteView,
    OrgAdminDashboardView,
    OrgDesignView,
    EinladungAnnehmenView,
    OrgEinladungCreateView,
    OrgEmailKonfigView,
    OrgMemberListView,
    OrgStartseitePageBuilderView,
    OrgStartseiteView,
    OrganisationSignupView,
    SuperadminOrganisationenView,
)

urlpatterns = [
    # Öffentliche Organisations-Startseite
    path("o/<slug:slug>/", OffentlicheStartseiteRedirectView.as_view(), name="org_public_home_legacy"),

    # Org-Selbstregistrierung
    path("organisationen/signup/", OrganisationSignupView.as_view(), name="org_signup"),

    # Org-Admin-Bereich
    path("organisationen/<slug:slug>/", OrgAdminDashboardView.as_view(), name="org_admin_dashboard"),
    path("organisationen/<slug:slug>/mitglieder/", OrgMemberListView.as_view(), name="org_members"),
    path("organisationen/einladung/<uuid:token>/", EinladungAnnehmenView.as_view(), name="org_invitation_accept"),
    path("organisationen/<slug:slug>/einladen/", OrgEinladungCreateView.as_view(), name="org_invite"),
    path("organisationen/<slug:slug>/email-konfiguration/", OrgEmailKonfigView.as_view(), name="org_email_config"),
    path("organisationen/<slug:slug>/design/", OrgDesignView.as_view(), name="org_design"),
    path("organisationen/<slug:slug>/startseite/", OrgStartseiteView.as_view(), name="org_startseite"),
    path("organisationen/<slug:slug>/startseite/pagebuilder/", OrgStartseitePageBuilderView.as_view(), name="org_startseite_pagebuilder"),

    # Superadmin
    path("superadmin/organisationen/", SuperadminOrganisationenView.as_view(), name="superadmin_orgs"),

    # Kanonische Mandanten-Startseite
    path("<slug:slug>/", OffentlicheStartseiteView.as_view(), name="org_public_home"),
]
