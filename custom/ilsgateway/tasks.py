import logging
from celery.task import task, periodic_task
from requests.exceptions import ConnectionError
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import UserRole
from custom.ilsgateway.api import ILSGatewayEndpoint
from custom.ilsgateway.commtrack import bootstrap_domain, sync_ilsgateway_webusers, sync_ilsgateway_smsusers


#@periodic_task(run_every=timedelta(days=1), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def users_task():
    projects = Domain.get_all()
    for project in projects:
        user_id = None
        if project.commtrack_settings and project.commtrack_settings.ilsgateway_config.is_configured:
            endpoint = ILSGatewayEndpoint.from_config(project.commtrack_settings.ilsgateway_config)
            try:

                for user in endpoint.get_webusers():
                    if user.email:
                        if not user.is_superuser:
                            setattr(user, 'role_id', UserRole.get_read_only_role_by_domain(project.name).get_id)
                        sync_ilsgateway_webusers(project, user)

                has_next = True
                next_url = None
                error = False
                while has_next:
                    next_url_params = next_url.split('?')[1] if next_url else None
                    meta, users = endpoint.get_smsusers(project.name, next_url_params)
                    for user in users:
                        try:
                            sync_ilsgateway_smsusers(project, user)
                            user_id = user.id
                        except Exception as e:
                            logging.error(e)
                            error = True
                    if not meta['next'] or error:
                        has_next = False
                    else:
                        next_url = meta['next']

                endpoint.confirm_migration(user_id, project.name, 'smsusers')
            except ConnectionError as e:
                logging.error(e)


@task
def bootstrap_domain_task(domain):
    return bootstrap_domain(domain)
