# run with: with open('data/case_search_FF_usage.py') as f: exec(f.read())

from corehq import toggles
from corehq.apps.accounting.models import Subscription
from corehq.apps.case_search.models import CaseSearchConfig
from corehq.apps.hqadmin.utils import get_download_url
from corehq.util.log import with_progress_bar
import csv
import io

from corehq.apps.linked_domain.models import DomainLink

output = io.StringIO()

header = ['Environment', 'Domain Name', 'Service Type', 'Plan Name', 'Case Search Enabled', 'Linked Domain Names']
writer = csv.DictWriter(output, fieldnames=header)
writer.writeheader()

domains = toggles.SYNC_SEARCH_CASE_CLAIM.get_enabled_domains()

for domain_name in with_progress_bar(domains, prefix="Domains"):
    subscription = Subscription.get_active_subscription_by_domain(domain_name)
    service_type = subscription.service_type if subscription else ''
    plan_name = subscription.plan_version.plan.name if subscription else ''

    domain_link = DomainLink.objects.filter(master_domain=domain_name, deleted=False)
    linked_domain_names = ','.join([ld.linked_domain for ld in domain_link])

    csc = CaseSearchConfig.objects.get_or_none(pk=domain_name)

    writer.writerow({
        'Environment': 'staging',
        'Domain Name': domain_name,
        'Service Type': service_type,
        'Plan Name': plan_name,
        'Case Search Enabled': csc and csc.enabled,
        'Linked Domain Names': linked_domain_names,
    })

output.seek(0)
url = get_download_url(io.BytesIO(output.read().encode('utf-8')), "case_search_usage.csv", content_type="text")
print(url)
