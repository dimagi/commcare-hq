import traceback

from celery.schedules import crontab
from django.utils import timezone
from django.utils.html import format_html

from corehq.apps.app_execution.api import execute_workflow
from corehq.apps.app_execution.models import AppWorkflowConfig
from corehq.apps.celery import periodic_task
from corehq.util import reverse
from corehq.util.log import send_HTML_email
from dimagi.utils.rate_limit import rate_limit


@periodic_task(run_every=crontab())  # run every minute
def run_app_workflows():

    for config in AppWorkflowConfig.objects.get_due():
        run_app_workflow(config, email_on_error=True)


def run_app_workflow(config, email_on_error=False):
    session = config.get_formplayer_session()
    log = config.appexecutionlog_set.create()
    try:
        success = execute_workflow(session, config.workflow)
    except Exception as e:
        log.success = False
        log.error = str(e)

        # rate limit to prevent spamming: 1 email per config per 10 minutes
        if email_on_error and rate_limit(
            f"task-execution-error-{config.pk}", actions_allowed=1, how_often=10 * 60
        ):
            _email_error(config, e, log)
    else:
        log.success = success
    finally:
        config.last_run = timezone.now()
        config.save()
        log.output = session.get_logs()
        log.completed = timezone.now()
        log.save()
    return log


def _email_error(config, e, log):
    url = reverse('app_execution:edit_workflow', args=[config.domain, config.pk], absolute=True)
    log_url = reverse('app_execution:workflow_log', args=[config.domain, log.pk], absolute=True)
    all_logs_url = reverse('app_execution:workflow_logs', args=[config.domain, config.pk], absolute=True)
    message = format_html(
        """Error executing workflow: <a href="{url}">{name}</a>
        <br><br>
        <p>Log: {log_url}</p>
        <p>All Logs: {all_logs_url}</p>
        <p><pre>{traceback}</pre></p>
        <p>Error:</p>
        <p>{error}</p>
        """,
        url=url,
        name=config.name,
        log_url=log_url,
        all_logs_url=all_logs_url,
        traceback=traceback.format_exc(),
        error=e,
    )
    send_HTML_email(
        f"App Execution Workflow Failure: {config.name}",
        config.notification_emails,
        message,
    )


@periodic_task(run_every=crontab(minute=0, hour=0))  # run every day at midnight
def clear_old_logs():
    AppWorkflowConfig.objects.filter(
        appexecutionlog__completed__lt=timezone.now() - timezone.timedelta(days=30)
    ).delete()
