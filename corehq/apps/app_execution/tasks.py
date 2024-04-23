import traceback

from celery.schedules import crontab
from django.utils import timezone

from corehq.apps.app_execution.api import execute_workflow
from corehq.apps.app_execution.models import AppWorkflowConfig
from corehq.apps.celery import periodic_task
from corehq.util import reverse
from corehq.util.log import send_HTML_email


@periodic_task(run_every=crontab(minute=0, hour=0))
def run_app_workflows():

    for config in AppWorkflowConfig.objects.get_due():
        try:
            session = config.get_formplayer_session()
            execute_workflow(session, config.workflow)
        except Exception as e:
            url = reverse('app_execution:edit_workflow', args=[config.pk], absolute=True)
            message = f"""Error executing workflow: <a href='{url}'>{config.name}</a>
            <br><br>
            <p>Error: {e}</p>
            <pre>{traceback.format_exc()}</pre>
            """
            send_HTML_email(
                f"App Execution Workflow Failure: {config.name}",
                config.notification_emails,
                message,
            )
        finally:
            config.last_run = timezone.now()
            config.save()
