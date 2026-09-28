from .models import Rolle


def rollen_context(request):
    if not request.user.is_authenticated:
        return {}

    active_org = getattr(request, "tenant_org", None)
    profile_qs = request.user.profile.filter(aktiv=True)
    if active_org and not request.user.is_superuser:
        profile_qs = profile_qs.filter(organisation=active_org)
    rollen = set(profile_qs.values_list("rolle", flat=True))
    ist_superadmin = request.user.is_superuser or request.user.groups.filter(name=Rolle.SUPERADMIN).exists()
    meine_org = None
    org_design = None

    if active_org and (request.user.is_superuser or profile_qs.exists()):
        meine_org = active_org
    elif Rolle.ORG_ADMIN in rollen:
        profil = (
            request.user.profile
            .filter(rolle=Rolle.ORG_ADMIN, aktiv=True)
            .select_related("organisation")
            .first()
        )
        if profil:
            meine_org = profil.organisation
    elif rollen:
        # Kein Org-Admin – erste aktive Org für Design-Kontext laden
        profil = (
            request.user.profile
            .filter(aktiv=True)
            .select_related("organisation")
            .first()
        )
        if profil:
            meine_org = profil.organisation

    if meine_org is not None:
        try:
            from apps.organisations.models import OrganisationDesign
            org_design = OrganisationDesign.objects.get(organisation=meine_org)
        except Exception:
            org_design = None

    return {
        "ist_superadmin": ist_superadmin,
        "ist_trainer": Rolle.TRAINER in rollen,
        "ist_exam_operator": Rolle.EXAM_OPERATOR in rollen,
        "ist_examiner": Rolle.EXAMINER in rollen,
        "ist_org_admin": Rolle.ORG_ADMIN in rollen,
        "meine_org": meine_org,
        "org_design": org_design,
    }
