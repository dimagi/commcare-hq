from django.db.models.signals import pre_save, post_delete
from django.dispatch import receiver

from corehq.apps.repeaters.models import FormRepeater
from corehq.apps.zapier.models import ZapierSubscription


@receiver(pre_save, sender=ZapierSubscription)
def zapier_subscription_pre_save(sender, instance, *args, **kwargs):
    if instance.pk:
        return
    repeater = FormRepeater(
        domain=instance.domain,
        url=instance.url,
        format='form_json',
        include_app_id_param=False,
        white_listed_form_xmlns=[instance.form_xmlns]
    )
    repeater.save()
    instance.repeater_id = repeater.get_id


@receiver(post_delete, sender=ZapierSubscription)
def zapier_subscription_post_delete(sender, instance, *args, **kwargs):
    repeater = FormRepeater.get(instance.repeater_id)
    repeater.delete()
