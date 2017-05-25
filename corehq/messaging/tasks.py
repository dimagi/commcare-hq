from corehq.apps.reminders import tasks as reminders_tasks
from corehq.apps.reminders.models import CaseReminderHandler
from corehq.apps.sms import tasks as sms_tasks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.celery_utils import no_result_task
from django.conf import settings


@no_result_task(queue=settings.CELERY_REMINDER_CASE_UPDATE_QUEUE, acks_late=True,
                default_retry_delay=5 * 60, max_retries=12, bind=True)
def sync_case_for_messaging(self, domain, case_id):
    try:
        _sync_case_for_messaging(domain, case_id)
    except Exception as e:
        self.retry(exc=e)


def _sync_case_for_messaging(domain, case_id):
    case = CaseAccessors(domain).get_case(case_id)
    sms_tasks.clear_case_caches(case)
    sms_tasks._sync_case_phone_number(case)
    handler_ids = CaseReminderHandler.get_handler_ids_for_case_post_save(case.domain, case.type)
    if handler_ids:
        reminders_tasks._process_case_changed_for_case(domain, case, handler_ids)
