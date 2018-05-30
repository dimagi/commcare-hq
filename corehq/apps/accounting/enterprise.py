from __future__ import absolute_import

import re

from datetime import datetime, timedelta
from django.utils.translation import ugettext as _

from dimagi.utils.dates import DateSpan

from corehq.apps.accounting.exceptions import EnterpriseReportError
from corehq.apps.accounting.models import DefaultProductPlan, Subscription
from corehq.apps.accounting.utils import get_default_domain_url
from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
from corehq.apps.es import forms as form_es
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter as EMWF
from corehq.apps.users.dbaccessors.all_commcare_users import (
    get_all_user_rows,
    get_mobile_user_count,
    get_web_user_count,
)
from corehq.apps.users.models import CommCareUser, WebUser


class EnterpriseReport(object):
    def __init__(self, couch_user):
        super(EnterpriseReport, self).__init__()
        self.couch_user = couch_user

    @property
    def headers(self):
        return ['Project Space Name', 'Project Name', 'Project URL']

    @classmethod
    def create(cls, slug, couch_user):
        if slug == 'domains':
            return EnterpriseDomainReport(couch_user)
        if slug == 'web_users':
            return EnterpriseWebUserReport(couch_user)
        if slug == 'mobile_users':
            return EnterpriseMobileWorkerReport(couch_user)
        if slug == 'form_submissions':
            return EnterpriseFormReport(couch_user)
        raise EnterpriseReportError(_("Unrecognized report '{}'").format(slug))

    def format_date(self, date):
        return date.strftime('%Y/%m/%d %H:%M:%S') if date else ''

    def domain_properties(self, domain):
        return [
            domain.name,
            domain.hr_name,
            get_default_domain_url(domain.name),
        ]

    def rows_for_domain(self, domain):
        raise NotImplementedError("Subclasses should override this")


class EnterpriseDomainReport(EnterpriseReport):
    def __init__(self, couch_user):
        super(EnterpriseDomainReport, self).__init__(couch_user)

    @property
    def headers(self):
        headers = super(EnterpriseDomainReport, self).headers
        return ['Plan', '# of Mobile Users', '# of Web Users'] + headers

    def rows_for_domain(self, domain):
        subscription = Subscription.get_active_subscription_by_domain(domain.name)
        plan_version = subscription.plan_version if subscription else DefaultProductPlan.get_default_plan_version()
        return [[
            plan_version.plan.name,
            str(get_mobile_user_count(domain.name, include_inactive=False)),
            str(get_web_user_count(domain.name, include_inactive=False)),
        ] + self.domain_properties(domain)]


class EnterpriseWebUserReport(EnterpriseReport):
    def __init__(self, couch_user):
        super(EnterpriseWebUserReport, self).__init__(couch_user)

    @property
    def headers(self):
        headers = super(EnterpriseWebUserReport, self).headers
        return ['Name', 'Email Address', 'Role', 'Last Login'] + headers

    def rows_for_domain(self, domain):
        rows = []
        for user in get_all_user_rows(domain.name, include_web_users=True, include_mobile_users=False,
                                      include_inactive=False, include_docs=True):
            user = WebUser.wrap(user['doc'])
            rows.append([
                user.full_name,
                user.username,
                user.role_label(domain.name),
                self.format_date(user.last_login),
            ] + self.domain_properties(domain))
        return rows


class EnterpriseMobileWorkerReport(EnterpriseReport):
    def __init__(self, couch_user):
        super(EnterpriseMobileWorkerReport, self).__init__(couch_user)

    @property
    def headers(self):
        headers = super(EnterpriseMobileWorkerReport, self).headers
        return ['Username', 'Name', 'Last Sync', 'Last Submission', 'CommCare Version'] + headers

    def rows_for_domain(self, domain):
        rows = []
        for user in get_all_user_rows(domain.name, include_web_users=False, include_mobile_users=True,
                                      include_inactive=False, include_docs=True):
            user = CommCareUser.wrap(user['doc'])
            rows.append([
                re.sub(r'@.*', '', user.username),
                user.full_name,
                self.format_date(user.reporting_metadata.last_sync_for_user.sync_date),
                self.format_date(user.reporting_metadata.last_submission_for_user.submission_date),
                user.reporting_metadata.last_submission_for_user.commcare_version or '',
            ] + self.domain_properties(domain))
        return rows


class EnterpriseFormReport(EnterpriseReport):
    def __init__(self, couch_user):
        super(EnterpriseFormReport, self).__init__(couch_user)
        self.window = 7

    @property
    def headers(self):
        headers = super(EnterpriseFormReport, self).headers
        return ['Form Name', 'Submitted', 'App Name', 'Mobile User'] + headers

    def rows_for_domain(self, domain):
        time_filter = form_es.submitted
        datespan = DateSpan(datetime.now() - timedelta(days=self.window), datetime.utcnow())
        apps = get_brief_apps_in_domain(domain.name)
        apps = {a.id: a.name for a in apps}

        users_filter = form_es.user_id(EMWF.user_es_query(domain.name,
                                       ['t__0'],  # All mobile workers
                                       self.couch_user)
                        .values_list('_id', flat=True))
        query = (form_es.FormES()
                 .domain(domain.name)
                 .filter(time_filter(gte=datespan.startdate,
                                     lt=datespan.enddate_adjusted))
                 .filter(users_filter))
        rows = []
        for hit in query.run().hits:
            username = hit['form']['meta']['username']
            submitted = self.format_date(datetime.strptime(hit['received_on'][:19], '%Y-%m-%dT%H:%M:%S'))
            rows.append([
                hit['form']['@name'],
                submitted,
                apps[hit['app_id']] if hit['app_id'] in apps else 'App not found',
                username,
            ] + self.domain_properties(domain))
        return rows
