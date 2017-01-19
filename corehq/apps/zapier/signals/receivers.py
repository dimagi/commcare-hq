from django.db.models.signals import pre_save, post_delete
from django.dispatch import receiver

from corehq.apps.repeaters.models import FormRepeater, CaseRepeater
from corehq.apps.zapier.models import ZapierSubscription


@receiver(pre_save, sender=ZapierSubscription)
def zapier_subscription_pre_save(sender, instance, *args, **kwargs):
    """
    Creates a repeater object corresponding to the type of trigger (form or case)
    """
    if instance.pk:
        return

    if instance.event_name == "new_form":
        repeater = FormRepeater(
            domain=instance.domain,
            url=instance.url,
            format='form_json',
            include_app_id_param=False,
            white_listed_form_xmlns=[instance.form_xmlns]
        )

    elif instance.event_name == "new_case":
        repeater = CaseRepeater(
            domain=instance.domain,
            url=instance.url,
            format='case_json',
            white_listed_case_types=[instance.case_type],
        )

    repeater.save()
    instance.repeater_id = repeater.get_id


@receiver(post_delete, sender=ZapierSubscription)
def zapier_subscription_post_delete(sender, instance, *args, **kwargs):
    """
    Deletes the repeater object when the corresponding zap is turned off
    """
    if instance.event_name == "new_form":
        repeater = FormRepeater.get(instance.repeater_id)
    elif instance.event_name == "new_case":
        repeater = CaseRepeater.get(instance.repeater_id)
    repeater.delete()
