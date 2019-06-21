from __future__ import absolute_import
from __future__ import unicode_literals

import re

from datetime import datetime, timedelta
from django.utils.translation import ugettext as _
from memoized import memoized

from dimagi.utils.dates import DateSpan

from couchforms.analytics import get_last_form_submission_received
from corehq.apps.accounting.exceptions import EnterpriseReportError
from corehq.apps.accounting.models import BillingAccount, Subscription
from corehq.apps.accounting.utils import get_default_domain_url
from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
from corehq.apps.domain.models import Domain
from corehq.apps.domain.calculations import sms_in_in_last
from corehq.apps.es import forms as form_es
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter as EMWF
from corehq.apps.users.dbaccessors.all_commcare_users import (
    get_all_user_rows,
    get_mobile_user_count,
    get_web_user_count,
)
from corehq.apps.users.models import CouchUser
from corehq.util.quickcache import quickcache


class EnterpriseReport(object):
    DOMAINS = 'domains'
    WEB_USERS = 'web_users'
    MOBILE_USERS = 'mobile_users'
    FORM_SUBMISSIONS = 'form_submissions'

    title = _('Enterprise Report')
    subtitle = ''

    def __init__(self, account_id, couch_user):
        super(EnterpriseReport, self).__init__()
        self.account = BillingAccount.objects.get(id=account_id)
        self.couch_user = couch_user
        self.slug = None

    @property
    def headers(self):
        return [_('Project Space Name'), _('Project Name'), _('Project URL')]

    @property
    def filename(self):
        return "{} ({}) {}.csv".format(self.account.name, self.title, datetime.utcnow().strftime('%Y%m%d %H%M%S'))

    @classmethod
    def create(cls, slug, account_id, couch_user):
        if slug == cls.DOMAINS:
            report = EnterpriseDomainReport(account_id, couch_user)
        if slug == cls.WEB_USERS:
            report = EnterpriseWebUserReport(account_id, couch_user)
        if slug == cls.MOBILE_USERS:
            report = EnterpriseMobileWorkerReport(account_id, couch_user)
        if slug == cls.FORM_SUBMISSIONS:
            report = EnterpriseFormReport(account_id, couch_user)
        if report:
            report.slug = slug
            return report
        raise EnterpriseReportError(_("Unrecognized report '{}'").format(slug))

    def format_date(self, date):
        return date.strftime('%Y/%m/%d %H:%M:%S') if date else ''

    def domain_properties(self, domain_obj):
        return [
            domain_obj.name,
            domain_obj.hr_name,
            get_default_domain_url(domain_obj.name),
        ]

    def rows_for_domain(self, domain_obj):
        raise NotImplementedError("Subclasses should override this")

    def total_for_domain(self, domain_obj):
        raise NotImplementedError("Subclasses should override this")

    @memoized
    def domains(self):
        subscriptions = Subscription.visible_objects.filter(account_id=self.account.id, is_active=True)
        domain_names = set(s.subscriber.domain for s in subscriptions)
        return [Domain.get_by_name(name) for name in domain_names]

    @property
    def rows(self):
        rows = []
        for domain_obj in self.domains():
            rows += self.rows_for_domain(domain_obj)
        return rows

    @property
    def total(self):
        total = 0
        for domain_obj in self.domains():
            total += self.total_for_domain(domain_obj)
        return total


class EnterpriseDomainReport(EnterpriseReport):
    title = _('Project Spaces')

    def __init__(self, account_id, couch_user):
        super(EnterpriseDomainReport, self).__init__(account_id, couch_user)

    @property
    def headers(self):
        headers = super(EnterpriseDomainReport, self).headers
        return [_('Created On [UTC]'), _('# of Apps'), _('# of Mobile Users'), _('# of Web Users'),
                _('# of SMS (last 30 days)'), _('Last Form Submission [UTC]')] + headers

    def rows_for_domain(self, domain_obj):
        return [[
            self.format_date(domain_obj.date_created),
            len(domain_obj.applications()),
            get_mobile_user_count(domain_obj.name, include_inactive=False),
            get_web_user_count(domain_obj.name, include_inactive=False),
            sms_in_in_last(domain_obj.name, 30),
            self.format_date(get_last_form_submission_received(domain_obj.name)),
        ] + self.domain_properties(domain_obj)]

    def total_for_domain(self, domain_obj):
        return 1


class EnterpriseWebUserReport(EnterpriseReport):
    title = _('Web Users')

    def __init__(self, account_id, couch_user):
        super(EnterpriseWebUserReport, self).__init__(account_id, couch_user)

    @property
    def headers(self):
        headers = super(EnterpriseWebUserReport, self).headers
        return [_('Name'), _('Email Address'), _('Role'), _('Last Login [UTC]'),
                _('Last Access Date [UTC]')] + headers

    def rows_for_domain(self, domain_obj):
        rows = []
        for user in get_all_user_rows(domain_obj.name, include_web_users=True, include_mobile_users=False,
                                      include_inactive=False, include_docs=True):
            user = CouchUser.wrap_correctly(user['doc'])
            domain_membership = user.get_domain_membership(domain_obj.name)
            last_accessed_domain = None
            if domain_membership:
                last_accessed_domain = domain_membership.last_accessed
            rows.append(
                [
                    user.full_name,
                    user.username,
                    user.role_label(domain_obj.name),
                    self.format_date(user.last_login),
                    last_accessed_domain
                ]
                + self.domain_properties(domain_obj))
        return rows

    def total_for_domain(self, domain_obj):
        return get_web_user_count(domain_obj.name, include_inactive=False)


class EnterpriseMobileWorkerReport(EnterpriseReport):
    title = _('Mobile Workers')

    def __init__(self, account_id, couch_user):
        super(EnterpriseMobileWorkerReport, self).__init__(account_id, couch_user)

    @property
    def headers(self):
        headers = super(EnterpriseMobileWorkerReport, self).headers
        return [_('Username'), _('Name'), _('Created Date [UTC]'), _('Last Sync [UTC]'),
                _('Last Submission [UTC]'), _('CommCare Version')] + headers

    def rows_for_domain(self, domain_obj):
        rows = []
        for user in get_all_user_rows(domain_obj.name, include_web_users=False, include_mobile_users=True,
                                      include_inactive=False, include_docs=True):
            user = CouchUser.wrap_correctly(user['doc'])
            rows.append([
                re.sub(r'@.*', '', user.username),
                user.full_name,
                self.format_date(user.created_on),
                self.format_date(user.reporting_metadata.last_sync_for_user.sync_date),
                self.format_date(user.reporting_metadata.last_submission_for_user.submission_date),
                user.reporting_metadata.last_submission_for_user.commcare_version or '',
            ] + self.domain_properties(domain_obj))
        return rows

    def total_for_domain(self, domain_obj):
        return get_mobile_user_count(domain_obj.name, include_inactive=False)


class EnterpriseFormReport(EnterpriseReport):
    title = _('Mobile Form Submissions')

    def __init__(self, account_id, couch_user):
        super(EnterpriseFormReport, self).__init__(account_id, couch_user)
        self.window = 30
        self.subtitle = _("past {} days").format(self.window)

    @property
    def headers(self):
        headers = super(EnterpriseFormReport, self).headers
        return [_('Form Name'), _('Submitted [UTC]'), _('App Name'), _('Mobile User')] + headers

    @quickcache(['self.account.id', 'domain_name'], timeout=60)
    def hits(self, domain_name):
        time_filter = form_es.submitted
        datespan = DateSpan(datetime.now() - timedelta(days=self.window), datetime.utcnow())

        users_filter = form_es.user_id(EMWF.user_es_query(domain_name,
                                       ['t__0'],  # All mobile workers
                                       self.couch_user)
                        .values_list('_id', flat=True))
        query = (form_es.FormES()
                 .domain(domain_name)
                 .filter(time_filter(gte=datespan.startdate,
                                     lt=datespan.enddate_adjusted))
                 .filter(users_filter))
        return query.run().hits

    def rows_for_domain(self, domain_obj):
        apps = get_brief_apps_in_domain(domain_obj.name)
        apps = {a.id: a.name for a in apps}
        rows = []
        for hit in self.hits(domain_obj.name):
            username = hit['form']['meta']['username']
            submitted = self.format_date(datetime.strptime(hit['received_on'][:19], '%Y-%m-%dT%H:%M:%S'))
            rows.append([
                hit['form']['@name'],
                submitted,
                apps[hit['app_id']] if hit['app_id'] in apps else _('App not found'),
                username,
            ] + self.domain_properties(domain_obj))
        return rows

    def total_for_domain(self, domain_obj):
        return len(self.hits(domain_obj.name))
