from __future__ import absolute_import
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.reminders import tasks as reminders_tasks
from corehq.apps.reminders.models import CaseReminderHandler
from corehq.apps.sms import tasks as sms_tasks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.messaging.scheduling.util import utcnow
from corehq.util.celery_utils import no_result_task
from dimagi.utils.couch import CriticalSection
from django.conf import settings


def get_sync_key(case_id):
    return 'sync-case-for-messaging-%s' % case_id


@no_result_task(queue=settings.CELERY_REMINDER_CASE_UPDATE_QUEUE, acks_late=True,
                default_retry_delay=5 * 60, max_retries=12, bind=True)
def sync_case_for_messaging(self, domain, case_id):
    try:
        with CriticalSection([get_sync_key(case_id)], timeout=5 * 60):
            _sync_case_for_messaging(domain, case_id)
    except Exception as e:
        self.retry(exc=e)


def _sync_case_for_messaging(domain, case_id):
    case = CaseAccessors(domain).get_case(case_id)
    sms_tasks.clear_case_caches(case)

    if settings.SERVER_ENVIRONMENT != 'icds':
        sms_tasks._sync_case_phone_number(case)

    handler_ids = CaseReminderHandler.get_handler_ids_for_case_post_save(case.domain, case.type)
    if handler_ids:
        reminders_tasks._process_case_changed_for_case(domain, case, handler_ids)

    rules = AutomaticUpdateRule.by_domain_cached(case.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)
    rules_by_case_type = AutomaticUpdateRule.organize_rules_by_case_type(rules)
    for rule in rules_by_case_type.get(case.type, []):
        rule.run_rule(case, utcnow())
