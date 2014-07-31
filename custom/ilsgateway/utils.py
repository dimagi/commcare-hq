from datetime import datetime
from corehq.apps.domain.models import Domain

GROUPS = ('A', 'B', 'C')

def get_current_group():
    month = datetime.utcnow().month
    return GROUPS[(month+2) % 3]

def send_for_all_domains(date, fn):
    for domain in Domain.get_all():
        #TODO Merge with ILSGateway integration?
        #ilsgateway_config = ILSGatewayConfig.for_domain(domain.name)
        #if ilsgateway_config and ilsgateway_config.enabled:
        fn(domain.name, date)