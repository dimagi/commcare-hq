import logging
from celery.task import task, periodic_task
from datetime import timedelta
from requests.exceptions import ConnectionError
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import UserRole
from custom.ilsgateway.api import ILSGatewayEndpoint
from custom.ilsgateway.commtrack import bootstrap_domain, sync_ilsgateway_webusers
import settings


@periodic_task(run_every=timedelta(days=1), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def users_task():
    projects = Domain.get_all()
    for project in projects:
        if project.commtrack_settings and project.commtrack_settings.ilsgateway_config.is_configured:
            endpoint = ILSGatewayEndpoint.from_config(project.commtrack_settings.ilsgateway_config)
            try:
                for user in endpoint.get_webusers():
                    if user.email:
                        if not user.is_superuser:
                            setattr(user, 'role_id', UserRole.get_read_only_role_by_domain(project.name).get_id)
                        sync_ilsgateway_webusers(project, user)
            except ConnectionError as e:
                logging.error(e)


@task
def bootstrap_domain_task(domain):
    return bootstrap_domain(domain)
