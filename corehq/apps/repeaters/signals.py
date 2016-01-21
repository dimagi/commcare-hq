from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from casexml.apps.case.xform import is_device_report
from couchforms.signals import successful_form_received


def create_form_repeat_records(sender, xform, **kwargs):
    from corehq.apps.repeaters.models import FormRepeater
    create_repeat_records(FormRepeater, xform)


def create_case_repeat_records(sender, case, **kwargs):
    from corehq.apps.repeaters.models import CaseRepeater
    create_repeat_records(CaseRepeater, case)


def create_short_form_repeat_records(sender, xform, **kwargs):
    from corehq.apps.repeaters.models import ShortFormRepeater
    create_repeat_records(ShortFormRepeater, xform)


def create_repeat_records(repeater_cls, payload):
    domain = payload.domain
    if domain:
        repeaters = repeater_cls.by_domain(domain)
        for repeater in repeaters:
            repeater.register(payload)


successful_form_received.connect(create_form_repeat_records)
successful_form_received.connect(create_short_form_repeat_records)
case_post_save.connect(create_case_repeat_records, CommCareCase)
