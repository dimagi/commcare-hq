from __future__ import absolute_import

from django.utils.translation import ugettext as _

from corehq.apps.accounting.exceptions import EnterpriseReportError
from corehq.apps.accounting.models import DefaultProductPlan, Subscription
from corehq.apps.accounting.utils import get_default_domain_url
from corehq.apps.users.dbaccessors.all_commcare_users import (
    get_all_user_rows,
    get_mobile_user_count,
    get_web_user_count,
)


class EnterpriseReport(object):
    def __init__(self):
        super(EnterpriseReport, self).__init__()

    @property
    def headers(self):
        return ['Project Space Name', 'Project Name', 'Project URL']

    @classmethod
    def create(cls, slug):
        if slug == 'domains':
            return EnterpriseDomainReport()
        if slug == 'web_users':
            return EnterpriseWebUserReport()
        if slug == 'mobile_users':
            return EnterpriseMobileWorkerReport()
        if slug == 'form_submissions':
            return EnterpriseFormReport()
        raise EnterpriseReportError(_("Unrecognized report '{}'").format(slug))

    def domain_properties(self, domain):
        return [
            domain.name,
            domain.hr_name,
            get_default_domain_url(domain.name),
        ]

    def rows_for_domain(self, domain):
        return [self.domain_properties(domain)]


class EnterpriseDomainReport(EnterpriseReport):
    def __init__(self):
        super(EnterpriseDomainReport, self).__init__()

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
    def __init__(self):
        super(EnterpriseWebUserReport, self).__init__()

    @property
    def headers(self):
        headers = super(EnterpriseWebUserReport, self).headers
        return ['Name', 'Email Address', 'Role', 'Last Login'] + headers


class EnterpriseMobileWorkerReport(EnterpriseReport):
    def __init__(self):
        super(EnterpriseMobileWorkerReport, self).__init__()

    @property
    def headers(self):
        headers = super(EnterpriseMobileWorkerReport, self).headers
        return ['Username', 'Name', 'Last Sync', 'Last Submission', 'CommCare Version'] + headers


class EnterpriseFormReport(EnterpriseReport):
    def __init__(self):
        super(EnterpriseFormReport, self).__init__()

    @property
    def headers(self):
        headers = super(EnterpriseFormReport, self).headers
        return ['Form Name', 'Submitted', 'App Name', 'Mobile User'] + headers
