import time

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver, dispatcher

from corehq.form_processor.signals import sql_case_post_save
from corehq.util.metrics import metrics_counter
from couchforms.signals import successful_form_received

from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.signals import commcare_user_post_save
from corehq.form_processor.models import CommCareCase
from corehq.motech.repeaters.models import (
    CreateCaseRepeater,
    DataSourceRepeater,
    DataRegistryCaseUpdateRepeater,
    ReferCaseRepeater,
    UpdateCaseRepeater,
    domain_can_forward,
)
from dimagi.utils.logging import notify_exception

ucr_data_source_updated = dispatcher.Signal()


def create_form_repeat_records(sender, xform, **kwargs):
    from corehq.motech.repeaters.models import FormRepeater
    if not xform.is_duplicate:
        create_repeat_records(FormRepeater, xform)


def create_case_repeat_records(sender, case, **kwargs):
    from corehq.motech.repeaters.models import CaseRepeater
    from corehq.motech.repeaters.expression.repeaters import CaseExpressionRepeater
    create_repeat_records(CaseRepeater, case)
    create_repeat_records(CreateCaseRepeater, case)
    create_repeat_records(UpdateCaseRepeater, case)
    create_repeat_records(ReferCaseRepeater, case)
    create_repeat_records(CaseExpressionRepeater, case)


def create_short_form_repeat_records(sender, xform, **kwargs):
    from corehq.motech.repeaters.models import ShortFormRepeater
    if not xform.is_duplicate:
        create_repeat_records(ShortFormRepeater, xform)


def create_repeat_records(repeater_cls, payload):
    # As a temporary fix for https://dimagi-dev.atlassian.net/browse/SUPPORT-12244
    # Make a serious attempt to retry creating the repeat record
    # The real fix is to figure out why the form reprocessing system
    # isn't resulting in the signal getting re-fired and the repeat record getting created.
    for sleep_length in [.5, 1, 2, 4, 8] if not settings.UNIT_TESTING else [0, 0]:
        try:
            _create_repeat_records(repeater_cls, payload)
        except Exception:
            notify_exception(None, "create_repeat_records had an error resulting in a retry")
            metrics_counter('commcare.repeaters.error_creating_record', tags={
                'domain': payload.domain,
                'repeater_type': repeater_cls._repeater_type,
            })
            time.sleep(sleep_length)
        else:
            return
    metrics_counter('commcare.repeaters.failed_to_create_record', tags={
        'domain': payload.domain,
        'repeater_type': repeater_cls._repeater_type,
    })


def _create_repeat_records(repeater_cls, payload, fire_synchronously=False):
    repeater_name = repeater_cls.__module__ + '.' + repeater_cls._repeater_type
    if settings.REPEATERS_WHITELIST is not None and repeater_name not in settings.REPEATERS_WHITELIST:
        return
    domain = payload.domain

    if domain_can_forward(domain):
        repeaters = repeater_cls.objects.by_domain(domain)
        for repeater in repeaters:
            repeater.register(payload, fire_synchronously=fire_synchronously)


@receiver(commcare_user_post_save, dispatch_uid="create_user_repeat_records")
def create_user_repeat_records(sender, couch_user, **kwargs):
    from corehq.motech.repeaters.models import UserRepeater
    create_repeat_records(UserRepeater, couch_user)


@receiver(post_save, sender=SQLLocation, dispatch_uid="create_location_repeat_records")
def create_location_repeat_records(sender, raw=False, **kwargs):
    from corehq.motech.repeaters.models import LocationRepeater
    if raw:
        return
    create_repeat_records(LocationRepeater, kwargs['instance'])


@receiver(sql_case_post_save, sender=CommCareCase, dispatch_uid="fire_synchronous_repeaters")
def fire_synchronous_case_repeaters(sender, case, **kwargs):
    """These repeaters need to fire synchronously since the changes they make to cases
    must reflect by the end of form submission processing
    """
    _create_repeat_records(DataRegistryCaseUpdateRepeater, case, fire_synchronously=True)


def create_data_source_updated_repeat_record(sender, **kwargs):
    """Creates a transaction log for the datasource that changed"""
    create_repeat_records(DataSourceRepeater, kwargs["update_log"])


successful_form_received.connect(create_form_repeat_records)
successful_form_received.connect(create_short_form_repeat_records)
sql_case_post_save.connect(create_case_repeat_records, CommCareCase)
ucr_data_source_updated.connect(create_data_source_updated_repeat_record)
