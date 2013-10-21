from celery.task import task
from custom.openlmis.commtrack import bootstrap_domain


@task
def bootstrap_domain_task(domain):
    return bootstrap_domain(domain)

