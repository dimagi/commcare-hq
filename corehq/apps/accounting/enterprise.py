from __future__ import absolute_import

from django.utils.translation import ugettext as _

from corehq.apps.accounting.exceptions import EnterpriseReportError


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


class EnterpriseDomainReport(EnterpriseReport):
    def __init__(self):
        super(EnterpriseDomainReport, self).__init__()

    @property
    def headers(self):
        headers = super(EnterpriseDomainReport, self).headers
        return ['Plan', '# of Mobile Users', '# of Web Users'] + headers


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
