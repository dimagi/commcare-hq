from __future__ import absolute_import
from __future__ import unicode_literals

from django.conf import settings

from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from corehq.messaging.tasks import sync_case_for_messaging
from corehq.form_processor.models import CommCareCaseSQL
from corehq.form_processor.signals import sql_case_post_save
from dimagi.utils.logging import notify_exception


def messaging_case_changed_receiver(sender, case, **kwargs):
    try:
        sync_case_for_messaging.delay(case.domain, case.case_id)
    except Exception:
        notify_exception(
            None,
            message="Could not create messaging case changed task. Is RabbitMQ running?"
        )


def connect_signals():
    if settings.SYNC_CASE_FOR_MESSAGING_ON_SAVE:
        case_post_save.connect(
            messaging_case_changed_receiver,
            CommCareCase,
            dispatch_uid='messaging_couch_case_receiver'
        )
        sql_case_post_save.connect(
            messaging_case_changed_receiver,
            CommCareCaseSQL,
            dispatch_uid='messaging_sql_case_receiver'
        )
