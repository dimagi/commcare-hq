from corehq.apps.smsforms.util import critical_section_for_smsforms_sessions
from corehq.util.celery_utils import no_result_task


@no_result_task(queue='reminder_queue')
def handle_due_survey_action(domain, contact_id, session_id):
    with critical_section_for_smsforms_sessions(contact_id):
        pass
