from django.dispatch import Signal, receiver
from django.db.models.signals import post_save
from .models import AllowedUCRExpressionSettings

commcare_domain_post_save = Signal()  # providing args: domain


@receiver(post_save, sender=AllowedUCRExpressionSettings)
def invalide_cache(sender, **kwargs):
    AllowedUCRExpressionSettings.get_allowed_ucr_expressions.clear(
        AllowedUCRExpressionSettings,
        kwargs["instance"].domain
    )
