import csv
import datetime
import io
import uuid

from django.db.models import Q
from django.utils.translation import gettext as _

from dimagi.utils.couch.cache.cache_core import get_redis_client

from corehq.apps.accounting.models import BillingAccount
from corehq.apps.celery import task
from corehq.apps.enterprise.enterprise import EnterpriseReport
from corehq.apps.enterprise.models import (
    EnterpriseMobileWorkerSettings,
    EnterprisePermissions,
)
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.users.models import DeactivateMobileWorkerTrigger
from corehq.const import ONE_DAY
from corehq.util.metrics import metrics_gauge
from corehq.util.metrics.const import MPM_LIVESUM
from corehq.util.view_utils import absolute_reverse


@task(serializer='pickle', queue="email_queue")
def email_enterprise_report(domain: str, slug, couch_user):
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
    send_html_email_async(
        subject,
        couch_user.get_email(),
        body,
        domain=domain,
        use_domain_gateway=True,
    )


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


@task()
def auto_deactivate_mobile_workers():
    time_started = datetime.datetime.utcnow()
    date_deactivation = datetime.date.today()
    for emw_setting in EnterpriseMobileWorkerSettings.objects.filter(
        Q(enable_auto_deactivation=True) | Q(allow_custom_deactivation=True)
    ):
        for domain in emw_setting.account.get_domains():
            if emw_setting.enable_auto_deactivation:
                emw_setting.deactivate_mobile_workers_by_inactivity(domain)
            if emw_setting.allow_custom_deactivation:
                DeactivateMobileWorkerTrigger.deactivate_mobile_workers(
                    domain, date_deactivation=date_deactivation,
                )
    task_time = datetime.datetime.utcnow() - time_started
    metrics_gauge(
        'commcare.enterprise.tasks.auto_deactivate_mobile_workers',
        task_time.seconds,
        multiprocess_mode=MPM_LIVESUM
    )


@task(queue="export_download_queue")
def generate_enterprise_report(slug, billing_account_id, username, **kwargs):
    report = EnterpriseReport.create(slug, billing_account_id, username, **kwargs)

    rows = report.rows
    progress = ReportTaskProgress(slug, username)
    progress.set_data(rows)


class TaskProgress:
    STATUS_TIMEOUT = 600  # 10 minutes

    STATUS_COMPLETE = 'COMPLETE'
    STATUS_IN_PROGRESS = 'IN_PROGRESS'
    STATUS_NEW = 'NEW'

    def __init__(self, key, query_id=None):
        self.key = key
        self._query_id = query_id
        self.redis_client = get_redis_client()

    def get_status(self):
        if self._query_id:
            return self.STATUS_COMPLETE

        status_dict = self.redis_client.get(self.key)
        if not status_dict:
            return self.STATUS_NEW

        return status_dict['status']

    def start_task(self, task):
        status_dict = {
            'status': self.STATUS_IN_PROGRESS,
            'query_id': None,
            'error': None,
            'task': task,
        }

        self.redis_client.set(self.key, status_dict, timeout=self.STATUS_TIMEOUT)
        task.delay()

    def get_data(self):
        query_id = self.get_query_id()
        data = self.redis_client.get(query_id)
        if data is None:
            # Before raising an error for a missing value, ensure that the 'None' wasn't deliberately set
            if not self.redis_client.has_key(query_id):
                raise KeyError(query_id)

        self.redis_client.touch(query_id, timeout=self.STATUS_TIMEOUT)

        return data

    def set_data(self, data):
        if not self._query_id:
            self._query_id = uuid.uuid4().hex
        self.redis_client.set(self._query_id, data, timeout=self.STATUS_TIMEOUT)

        status_dict = self.redis_client.get(self.key)
        if status_dict is None:
            raise KeyError(self.key)
        status_dict['status'] = self.STATUS_COMPLETE
        status_dict['query_id'] = self._query_id
        self.redis_client.set(self.key, status_dict, timeout=self.STATUS_TIMEOUT)

    def get_query_id(self):
        if self._query_id:
            return self._query_id

        status_dict = self.redis_client.get(self.key)
        self._query_id = status_dict['query_id']
        return self._query_id

    def clear_status(self):
        self.redis_client.delete(self.key)  # clear status data to allow this key to be re-used

    def get_task(self):
        status_dict = self.redis_client.get(self.key)
        return status_dict.get('task', None) if status_dict else None


class ReportTaskProgress(TaskProgress):
    def __init__(self, slug, username, query_id=None, **kwargs):
        key = f'report-gen-status-{slug}.{username}'
        super().__init__(key, query_id=query_id)
