from celery.schedules import crontab

from corehq.apps.app_execution.api import execute_workflow
from corehq.apps.app_execution.models import AppWorkflowConfig
from corehq.apps.celery import periodic_task


@periodic_task(run_every=crontab(minute=0, hour=0))
def run_app_workflows():

    for config in AppWorkflowConfig.objects.get_due():
        session = config.get_formplayer_session()
        execute_workflow(session, config.workflow)
