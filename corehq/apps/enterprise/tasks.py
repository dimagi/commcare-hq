import csv
import io
import uuid

from django.utils.translation import ugettext as _

from celery.task import task

from dimagi.utils.couch.cache.cache_core import get_redis_client

from corehq.apps.accounting.models import BillingAccount
from corehq.apps.enterprise.enterprise import EnterpriseReport
from corehq.apps.enterprise.models import EnterprisePermissions
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.const import ONE_DAY
from corehq.util.view_utils import absolute_reverse


@task(serializer='pickle', queue="email_queue")
def email_enterprise_report(domain, slug, couch_user):
    account = BillingAccount.get_account_by_domain(domain)
    report = EnterpriseReport.create(slug, account.id, couch_user)

    # Generate file
    csv_file = io.StringIO()
    writer = csv.writer(csv_file)
    writer.writerow(report.headers)
    writer.writerows(report.rows)

    # Store file in redis
    hash_id = uuid.uuid4().hex
    redis = get_redis_client()
    redis.set(hash_id, csv_file.getvalue())
    redis.expire(hash_id, ONE_DAY)
    csv_file.close()

    # Send email
    url = absolute_reverse("enterprise_dashboard_download", args=[domain, report.slug, str(hash_id)])
    link = "<a href='{}'>{}</a>".format(url, url)
    subject = _("Enterprise Dashboard: {}").format(report.title)
    body = "The enterprise report you requested for the account {} is ready.<br>" \
           "You can download the data at the following link: {}<br><br>" \
           "Please remember that this link will only be active for 24 hours.".format(account.name, link)
    send_html_email_async(subject, couch_user.username, body)


@task
def clear_enterprise_permissions_cache_for_all_users(config_id, domain=None):
    try:
        config = EnterprisePermissions.objects.get(id=config_id)
    except EnterprisePermissions.DoesNotExist:
        return
    from corehq.apps.domain.views.base import get_enterprise_links_for_dropdown
    from corehq.apps.users.models import CouchUser
    domains = [domain] if domain else config.account.get_domains()
    for domain in domains:
        for user_id in CouchUser.ids_by_domain(domain):
            user = CouchUser.get_by_user_id(user_id)
            get_enterprise_links_for_dropdown.clear(user)
