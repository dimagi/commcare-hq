from corehq.util.celery_utils import no_result_task


@no_result_task(queue='reminder_queue')
def handle_due_survey_action(domain, connection_id, session_id):
    pass
