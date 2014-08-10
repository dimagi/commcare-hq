from celery.task import task, periodic_task
from custom.ilsgateway.commtrack import bootstrap_domain


#@periodic_task(run_every=timedelta(days=1), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
from custom.ilsgateway.models import ILSGatewayConfig


def migration_task():
    configs = ILSGatewayConfig.get_all_configs()
    for config in configs:
        if config.enabled:
            bootstrap_domain(config)


@task
def bootstrap_domain_task(domain):
    ilsgateway_config = ILSGatewayConfig.for_domain(domain)
    return bootstrap_domain(ilsgateway_config)
