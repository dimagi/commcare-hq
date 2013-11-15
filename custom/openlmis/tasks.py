from celery.schedules import crontab
from celery.task.base import periodic_task
from celery.task import task
from corehq import Domain
from custom.openlmis.api import OpenLMISEndpoint
from custom.openlmis.commtrack import bootstrap_domain, sync_requisition_from_openlmis
import settings

@periodic_task(run_every=crontab(minute=0, hour=1),queue=getattr(settings, 'CELERY_PERIODIC_QUEUE','celery'))
def check_requisition_updates():
    projects = Domain.get_all()
    for project in projects:
        if project.commtrack_enabled and project.commtrack_settings.openlmis_enabled:
            endpoint = OpenLMISEndpoint.from_config(project.commtrack_settings.openlmis_config)
            requisitions = endpoint.get_all_requisition_statuses()
            for requisition in requisitions:
                sync_requisition_from_openlmis(project.name, requisition.requisition_id, endpoint)

@task
def bootstrap_domain_task(domain):
    return bootstrap_domain(domain)

