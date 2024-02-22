import re
from datetime import datetime, timedelta

from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from memoized import memoized

from couchforms.analytics import get_last_form_submission_received
from dimagi.utils.dates import DateSpan

from corehq.apps.enterprise.exceptions import EnterpriseReportError
from corehq.apps.accounting.models import BillingAccount
from corehq.apps.accounting.utils import get_default_domain_url
from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
from corehq.apps.domain.calculations import sms_in_last
from corehq.apps.domain.models import Domain
from corehq.apps.es import forms as form_es
from corehq.apps.es.users import UserES
from corehq.apps.export.dbaccessors import ODataExportFetcher
from corehq.apps.users.dbaccessors import (
    get_all_user_rows,
    get_mobile_user_count,
    get_web_user_count,
)
from corehq.apps.users.models import CouchUser, Invitation
from corehq.util.quickcache import quickcache


class EnterpriseReport:
    DOMAINS = 'domains'
    WEB_USERS = 'web_users'
    MOBILE_USERS = 'mobile_users'
    FORM_SUBMISSIONS = 'form_submissions'
    ODATA_FEEDS = 'odata_feeds'

    title = _('Enterprise Report')
    subtitle = ''

    def __init__(self, account, couch_user):
        self.account = account
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
        account = BillingAccount.objects.get(id=account_id)
        report = None
        if slug == cls.DOMAINS:
            report = EnterpriseDomainReport(account, couch_user)
        elif slug == cls.WEB_USERS:
            report = EnterpriseWebUserReport(account, couch_user)
        elif slug == cls.MOBILE_USERS:
            report = EnterpriseMobileWorkerReport(account, couch_user)
        elif slug == cls.FORM_SUBMISSIONS:
            report = EnterpriseFormReport(account, couch_user)
        elif slug == cls.ODATA_FEEDS:
            report = EnterpriseODataReport(account, couch_user)

        if report:
            report.slug = slug
            return report
        else:
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
        return [Domain.get_by_name(name) for name in self.account.get_domains()]

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

    @property
    def headers(self):
        headers = super().headers
        return [_('Created On [UTC]'), _('# of Apps'), _('# of Mobile Users'), _('# of Web Users'),
                _('# of SMS (last 30 days)'), _('Last Form Submission [UTC]')] + headers

    def rows_for_domain(self, domain_obj):
        return [[
            self.format_date(domain_obj.date_created),
            len(domain_obj.applications()),
            get_mobile_user_count(domain_obj.name, include_inactive=False),
            get_web_user_count(domain_obj.name, include_inactive=False),
            sms_in_last(domain_obj.name, 30),
            self.format_date(get_last_form_submission_received(domain_obj.name)),
        ] + self.domain_properties(domain_obj)]

    def total_for_domain(self, domain_obj):
        return 1


class EnterpriseWebUserReport(EnterpriseReport):
    title = _('Web Users')

    @property
    def headers(self):
        headers = super().headers
        return [_('Email Address'), _('Name'), _('Role'), _('Last Login [UTC]'),
                _('Last Access Date [UTC]'), _('Status')] + headers

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
                    user.username,
                    user.full_name,
                    user.role_label(domain_obj.name),
                    self.format_date(user.last_login),
                    last_accessed_domain,
                    _('Active User')
                ]
                + self.domain_properties(domain_obj))
        for invite in Invitation.by_domain(domain_obj.name):
            rows.append(
                [
                    invite.email,
                    'N/A',
                    invite.get_role_name(),
                    'N/A',
                    'N/A',
                    _('Invited')
                ]
                + self.domain_properties(domain_obj))
        return rows

    def total_for_domain(self, domain_obj):
        return get_web_user_count(domain_obj.name, include_inactive=False)


class EnterpriseMobileWorkerReport(EnterpriseReport):
    title = _('Mobile Workers')

    @property
    def headers(self):
        headers = super().headers
        return [_('Username'), _('Name'), _('Email Address'), _('Role'), _('Created Date [UTC]'),
                _('Last Sync [UTC]'), _('Last Submission [UTC]'), _('CommCare Version'), _('User ID')] + headers

    def rows_for_domain(self, domain_obj):
        rows = []
        for user in get_all_user_rows(domain_obj.name, include_web_users=False, include_mobile_users=True,
                                      include_inactive=False, include_docs=True):
            user = CouchUser.wrap_correctly(user['doc'])
            rows.append([
                re.sub(r'@.*', '', user.username),
                user.full_name,
                user.email,
                user.role_label(domain_obj.name),
                self.format_date(user.created_on),
                self.format_date(user.reporting_metadata.last_sync_for_user.sync_date),
                self.format_date(user.reporting_metadata.last_submission_for_user.submission_date),
                user.reporting_metadata.last_submission_for_user.commcare_version or '',
                user.user_id
            ] + self.domain_properties(domain_obj))
        return rows

    def total_for_domain(self, domain_obj):
        return get_mobile_user_count(domain_obj.name, include_inactive=False)


class EnterpriseFormReport(EnterpriseReport):
    title = _('Mobile Form Submissions')

    def __init__(self, account, couch_user):
        super().__init__(account, couch_user)
        self.window = 30
        self.subtitle = _("past {} days").format(self.window)

    @property
    def headers(self):
        headers = super().headers
        return [_('Form Name'), _('Submitted [UTC]'), _('App Name'), _('Mobile User')] + headers

    def _query(self, domain_name):
        time_filter = form_es.submitted
        datespan = DateSpan(datetime.now() - timedelta(days=self.window), datetime.utcnow())

        users_filter = form_es.user_id(UserES().domain(domain_name).mobile_users().show_inactive()
                                    .values_list('_id', flat=True))

        query = (form_es.FormES()
                 .domain(domain_name)
                 .filter(time_filter(gte=datespan.startdate,
                                     lt=datespan.enddate_adjusted))
                 .filter(users_filter))
        return query

    @quickcache(['self.account.id', 'domain_name'], timeout=60)
    def hits(self, domain_name):
        return self._query(domain_name).run().hits

    def rows_for_domain(self, domain_obj):
        apps = get_brief_apps_in_domain(domain_obj.name)
        apps = {a.id: a.name for a in apps}
        rows = []
        for hit in self.hits(domain_obj.name):
            if hit['form'].get('#type') == 'system':
                continue
            username = hit['form']['meta']['username']
            submitted = self.format_date(datetime.strptime(hit['received_on'][:19], '%Y-%m-%dT%H:%M:%S'))
            rows.append([
                hit['form'].get('@name', _('Unnamed')),
                submitted,
                apps[hit['app_id']] if hit['app_id'] in apps else _('App not found'),
                username,
            ] + self.domain_properties(domain_obj))
        return rows

    def total_for_domain(self, domain_obj):
        return self._query(domain_obj.name).count()


class EnterpriseODataReport(EnterpriseReport):
    title = gettext_lazy('OData Feeds')
    MAXIMUM_EXPECTED_EXPORTS = 150

    def __init__(self, account, couch_user):
        super().__init__(account, couch_user)
        self.export_fetcher = ODataExportFetcher()

    @property
    def headers(self):
        headers = super().headers
        return [_('Odata feeds used'), _('Odata feeds available'), _('Report Names'),
            _('Number of rows')] + headers

    def total_for_domain(self, domain_obj):
        return self.export_fetcher.get_export_count(domain_obj.name)

    def rows_for_domain(self, domain_obj):
        export_count = self.total_for_domain(domain_obj)
        if export_count == 0 or export_count > self.MAXIMUM_EXPECTED_EXPORTS:
            return [self._get_domain_summary_line(domain_obj, export_count)]

        exports = self.export_fetcher.get_exports(domain_obj.name)

        export_line_counts = self._get_export_line_counts(exports)

        domain_summary_line = self._get_domain_summary_line(domain_obj, export_count, export_line_counts)
        individual_export_rows = self._get_individual_export_rows(exports, export_line_counts)

        rows = [domain_summary_line]
        rows.extend(individual_export_rows)
        return rows

    def _get_export_line_counts(self, exports):
        return {export._id: export.get_count() for export in exports}

    def _get_domain_summary_line(self, domain_obj, export_count, export_line_counts={}):
        if export_count > self.MAXIMUM_EXPECTED_EXPORTS:
            total_line_count = _('ERROR: Too many exports. Please contact customer service')
        else:
            total_line_count = sum(export_line_counts.values())

        return [
            export_count,
            domain_obj.get_odata_feed_limit(),
            None,  # Report Name
            total_line_count
        ] + self.domain_properties(domain_obj)

    def _get_individual_export_rows(self, exports, export_line_counts):
        rows = []

        for export in exports:
            count = export_line_counts[export._id]
            rows.append([
                None,  # OData feeds used
                None,  # OData feeds available
                export.name,
                count]
            )

        return rows
