from django.contrib.auth.models import Group
from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .models import Rolle


@receiver(post_migrate)
def ensure_role_groups(sender, **kwargs):
    if sender.label != "accounts":
        return
    for role in Rolle:
        Group.objects.get_or_create(name=role.value)
