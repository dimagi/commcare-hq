import traceback

from celery.schedules import crontab
from django.utils import timezone
from django.utils.html import format_html

from corehq.apps.app_execution.api import execute_workflow
from corehq.apps.app_execution.models import AppWorkflowConfig
from corehq.apps.celery import periodic_task
from corehq.util import reverse
from corehq.util.log import send_HTML_email


@periodic_task(run_every=crontab())  # run every minute
def run_app_workflows():

    for config in AppWorkflowConfig.objects.get_due():
        session = config.get_formplayer_session()
        log = config.appexecutionlog_set.create()
        try:
            execute_workflow(session, config.workflow)
        except Exception as e:
            log.success = False
            log.error = str(e)

            url = reverse('app_execution:edit_workflow', args=[config.pk], absolute=True)
            log_url = reverse('app_execution:workflow_log', args=[log.pk], absolute=True)
            message = format_html("""Error executing workflow: <a href="url}">{name}</a>
            <br><br>
            <p>Log: {log_url}</p>
            <p><pre>{traceback}</pre></p>
            <p>Error:</p>
            <p>{error}</p>
            """, url=url, name=config.name, log_url=log_url, error=e, traceback=traceback.format_exc())
            send_HTML_email(
                f"App Execution Workflow Failure: {config.name}",
                config.notification_emails,
                message,
            )
        else:
            log.success = True
        finally:
            config.last_run = timezone.now()
            config.save()
            log.output = session.log.getvalue()
            log.completed = timezone.now()
            log.save()
