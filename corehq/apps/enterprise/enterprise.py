from abc import ABC, abstractmethod
import re
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Count, Subquery, Q
from dimagi.ext.jsonobject import DateTimeProperty
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from memoized import memoized

from couchforms.analytics import get_last_form_submission_received
from dimagi.utils.dates import DateSpan

from corehq.apps.accounting.models import BillingAccount
from corehq.apps.accounting.utils import get_default_domain_url
from corehq.apps.app_manager.dbaccessors import get_app_ids_in_domain, get_brief_apps_in_domain
from corehq.apps.app_manager.models import Application
from corehq.apps.builds.utils import get_latest_version_at_time, is_out_of_date
from corehq.apps.builds.models import CommCareBuildConfig
from corehq.apps.domain.calculations import sms_in_last
from corehq.apps.domain.models import Domain
from corehq.apps.enterprise.exceptions import (
    EnterpriseReportError,
    TooMuchRequestedDataError,
)
from corehq.apps.enterprise.iterators import raise_after_max_elements
from corehq.apps.es import AppES, forms as form_es
from corehq.apps.es.users import UserES
from corehq.apps.export.dbaccessors import ODataExportFetcher
from corehq.apps.reports.util import (
    get_commcare_version_and_date_from_last_usage,
)
from corehq.apps.sms.models import SMS, OUTGOING, INCOMING
from corehq.apps.users.dbaccessors import (
    get_all_user_rows,
    get_mobile_user_count,
    get_web_user_count,
)
from corehq.apps.users.models import CouchUser, HQApiKey, Invitation, WebUser


class EnterpriseReport(ABC):
    DOMAINS = 'domains'
    WEB_USERS = 'web_users'
    MOBILE_USERS = 'mobile_users'
    FORM_SUBMISSIONS = 'form_submissions'
    ODATA_FEEDS = 'odata_feeds'
    COMMCARE_VERSION_COMPLIANCE = 'commcare_version_compliance'
    SMS = 'sms'
    API_USAGE = 'api_usage'
    TWO_FACTOR_AUTH = '2fa'
    APP_VERSION_COMPLIANCE = 'app_version_compliance'

    DATE_ROW_FORMAT = '%Y/%m/%d %H:%M:%S'

    @property
    @abstractmethod
    def title(self):
        pass

    @property
    @abstractmethod
    def total_description(self):
        """
        To provide a description of the total number we displayed in tile
        """
        pass

    def __init__(self, account, couch_user, **kwargs):
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
    def create(cls, slug, account_id, couch_user, **kwargs):
        account = BillingAccount.objects.get(id=account_id)
        report = None
        if slug == cls.DOMAINS:
            report = EnterpriseDomainReport(account, couch_user, **kwargs)
        elif slug == cls.WEB_USERS:
            report = EnterpriseWebUserReport(account, couch_user, **kwargs)
        elif slug == cls.MOBILE_USERS:
            report = EnterpriseMobileWorkerReport(account, couch_user, **kwargs)
        elif slug == cls.FORM_SUBMISSIONS:
            report = EnterpriseFormReport(account, couch_user, **kwargs)
        elif slug == cls.ODATA_FEEDS:
            report = EnterpriseODataReport(account, couch_user, **kwargs)
        elif slug == cls.COMMCARE_VERSION_COMPLIANCE:
            report = EnterpriseCommCareVersionReport(account, couch_user, **kwargs)
        elif slug == cls.SMS:
            report = EnterpriseSMSReport(account, couch_user, **kwargs)
        elif slug == cls.API_USAGE:
            report = EnterpriseAPIReport(account, couch_user, **kwargs)
        elif slug == cls.TWO_FACTOR_AUTH:
            report = Enterprise2FAReport(account, couch_user, **kwargs)
        elif slug == cls.APP_VERSION_COMPLIANCE:
            report = EnterpriseAppVersionComplianceReport(account, couch_user, **kwargs)

        if report:
            report.slug = slug
            return report
        else:
            raise EnterpriseReportError(_("Unrecognized report '{}'").format(slug))

    def format_date(self, date):
        return date.strftime(self.DATE_ROW_FORMAT) if date else ''

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

    title = gettext_lazy('Project Spaces')
    total_description = gettext_lazy('# of Project Spaces')

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

    title = gettext_lazy('Web Users')
    total_description = gettext_lazy('# of Web Users')

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
    title = gettext_lazy('Mobile Workers')
    total_description = gettext_lazy('# of Mobile Workers')

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
    title = gettext_lazy('Mobile Form Submissions')
    total_description = gettext_lazy('# of Mobile Form Submissions')

    MAXIMUM_USERS_PER_DOMAIN = getattr(settings, 'ENTERPRISE_REPORT_DOMAIN_USER_LIMIT', 20_000)
    MAXIMUM_ROWS_PER_REQUEST = getattr(settings, 'ENTERPRISE_REPORT_ROW_LIMIT', 1_000_000)
    MAX_DATE_RANGE_DAYS = 90

    def __init__(self, account, couch_user, start_date=None, end_date=None, num_days=30, include_form_id=False):
        super().__init__(account, couch_user)
        if not end_date:
            end_date = datetime.utcnow()
        elif isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date)

        if start_date:
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date)
            self.datespan = DateSpan(start_date, end_date)
        else:
            self.datespan = DateSpan(end_date - timedelta(days=num_days), end_date)

        if self.datespan.enddate - self.datespan.startdate > timedelta(days=self.MAX_DATE_RANGE_DAYS):
            raise TooMuchRequestedDataError(
                _('Date ranges with more than {} days are not supported').format(self.MAX_DATE_RANGE_DAYS)
            )

        self.include_form_id = include_form_id

    @property
    def headers(self):
        headers = super().headers
        headers = [_('Form ID')] if self.include_form_id else []
        headers.extend([_('Form Name'), _('Submitted [UTC]'), _('App Name'), _('Mobile User')] + headers)

        return headers

    def _query(self, domain_name):
        time_filter = form_es.submitted

        users_filter = form_es.user_id(
            UserES().domain(domain_name).mobile_users().show_inactive().size(self.MAXIMUM_USERS_PER_DOMAIN + 1)
            .values_list('_id', flat=True)
        )

        if len(users_filter) > self.MAXIMUM_USERS_PER_DOMAIN:
            raise TooMuchRequestedDataError(
                _('Domain {name} has too many users. Maximum allowed is: {amount}')
                .format(name=domain_name, amount=self.MAXIMUM_USERS_PER_DOMAIN)
            )

        query = (
            form_es.FormES()
            .domain(domain_name)
            .filter(time_filter(gte=self.datespan.startdate, lt=self.datespan.enddate_adjusted))
            .filter(users_filter)
        )
        return query

    def hits(self, domain_name):
        return raise_after_max_elements(
            self._query(domain_name).scroll(),
            self.MAXIMUM_ROWS_PER_REQUEST,
            self._generate_data_error()
        )

    def _generate_data_error(self):
        return TooMuchRequestedDataError(
            _('{name} contains too many rows. Maximum allowed is: {amount}. Please narrow the date range'
                ' to fetch a smaller amount of data').format(
                    name=self.account.name, amount=self.MAXIMUM_ROWS_PER_REQUEST)
        )

    @property
    def rows(self):
        total_rows = 0
        rows = []
        for domain_obj in self.domains():
            domain_rows = self.rows_for_domain(domain_obj)
            total_rows += len(domain_rows)
            if total_rows > self.MAXIMUM_ROWS_PER_REQUEST:
                raise self._generate_data_error()
            rows += domain_rows
        return rows

    def rows_for_domain(self, domain_obj):
        apps = get_brief_apps_in_domain(domain_obj.name)
        apps = {a.id: a.name for a in apps}
        rows = []

        for hit in self.hits(domain_obj.name):
            if hit['form'].get('#type') == 'system':
                continue
            username = hit['form']['meta']['username']
            submitted = self.format_date(datetime.strptime(hit['received_on'][:19], '%Y-%m-%dT%H:%M:%S'))
            row = [hit['_id']] if self.include_form_id else []
            row.extend([
                hit['form'].get('@name', _('Unnamed')),
                submitted,
                apps[hit['app_id']] if hit['app_id'] in apps else _('App not found'),
                username,
            ] + self.domain_properties(domain_obj))
            rows.append(row)
        return rows

    def total_for_domain(self, domain_obj):
        return self._query(domain_obj.name).count()


class EnterpriseODataReport(EnterpriseReport):
    title = gettext_lazy('OData Feeds')
    total_description = gettext_lazy('# of OData Feeds')

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


class EnterpriseCommCareVersionReport(EnterpriseReport):
    title = gettext_lazy('CommCare Version Compliance')
    total_description = gettext_lazy('% of Mobile Workers on the Latest CommCare Version')

    @property
    def headers(self):
        return [
            _('Mobile Worker'),
            _('Project Space'),
            _('Latest Version Available at Submission'),
            _('Version in Use'),
        ]

    @property
    def rows(self):
        rows = []
        config = CommCareBuildConfig.fetch()
        version_cache = {}
        for domain in self.account.get_domains():
            rows.extend(self.rows_for_domain(domain, config, version_cache))
        return rows

    @property
    def total(self):
        total_mobile_workers = 0
        total_up_to_date = 0
        config = CommCareBuildConfig.fetch()
        version_cache = {}

        def total_for_domain(domain):
            mobile_workers = get_mobile_user_count(domain, include_inactive=False)
            if mobile_workers == 0:
                return 0, 0
            outdated_users = len(self.rows_for_domain(domain, config, version_cache))
            return mobile_workers, outdated_users

        for domain in self.account.get_domains():
            domain_mobile_workers, outdated_users = total_for_domain(domain)
            total_mobile_workers += domain_mobile_workers
            total_up_to_date += domain_mobile_workers - outdated_users

        return _format_percentage_for_enterprise_tile(total_up_to_date, total_mobile_workers)

    def rows_for_domain(self, domain, config, cache):
        rows = []

        user_query = (UserES()
            .domain(domain)
            .mobile_users()
            .source([
                'username',
                'reporting_metadata.last_submission_for_user.commcare_version',
                'reporting_metadata.last_submission_for_user.submission_date',
                'last_device.commcare_version',
                'last_device.last_used'
            ]))

        for user in user_query.run().hits:
            last_submission = user.get('reporting_metadata', {}).get('last_submission_for_user', {})
            last_device = user.get('last_device', {})

            version_in_use, date_of_use = get_commcare_version_and_date_from_last_usage(last_submission,
                                                                                        last_device)

            if not version_in_use:
                continue

            latest_version_at_time_of_use = get_latest_version_at_time(config, date_of_use, cache)

            if is_out_of_date(version_in_use, latest_version_at_time_of_use):
                rows.append([
                    user['username'],
                    domain,
                    latest_version_at_time_of_use,
                    version_in_use,
                ])

        return rows


class EnterpriseSMSReport(EnterpriseReport):
    title = gettext_lazy('SMS Usage')
    total_description = gettext_lazy('# of SMS Sent')

    MAX_DATE_RANGE_DAYS = 90

    def __init__(self, account, couch_user, start_date=None, end_date=None, num_days=30):
        super().__init__(account, couch_user)

        if not end_date:
            end_date = datetime.utcnow()
        elif isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date)

        if start_date:
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date)
            self.datespan = DateSpan(start_date, end_date)
        else:
            self.datespan = DateSpan(end_date - timedelta(days=num_days), end_date)

        if self.datespan.enddate - self.datespan.startdate > timedelta(days=self.MAX_DATE_RANGE_DAYS):
            raise TooMuchRequestedDataError(
                _('Date ranges with more than {} days are not supported').format(self.MAX_DATE_RANGE_DAYS)
            )

    def total_for_domain(self, domain_obj):
        query = SMS.objects.filter(
            domain=domain_obj.name,
            processed=True,
            direction=OUTGOING,
            error=False,
            date__gte=self.datespan.startdate,
            date__lt=self.datespan.enddate_adjusted
        )

        return query.count()

    @property
    def headers(self):
        headers = [_('Project Space'), _('# Sent'), _('# Received'), _('# Errors')]

        return headers

    def rows_for_domain(self, domain_obj):
        results = SMS.objects.filter(
            domain=domain_obj.name,
            processed=True,
            date__gte=self.datespan.startdate,
            date__lt=self.datespan.enddate_adjusted
        ).values('direction', 'error').annotate(direction_count=Count('pk'))

        num_sent = sum([result['direction_count'] for result in results
                        if result['direction'] == OUTGOING and not result['error']])
        num_received = sum([result['direction_count'] for result in results
                            if result['direction'] == INCOMING and not result['error']])
        num_errors = sum([result['direction_count'] for result in results if result['error']])

        return [(domain_obj.name, num_sent, num_received, num_errors), ]


class EnterpriseAPIReport(EnterpriseReport):
    title = gettext_lazy('API Usage')
    total_description = gettext_lazy('# of Active API Keys')

    @property
    def headers(self):
        return [_('Web User'), _('API Key Name'), _('Scope'), _('Expiration Date [UTC]'), _('Created On [UTC]'),
                _('Last Used On [UTC]')]

    @property
    def rows(self):
        return [self._get_api_key_row(api_key) for api_key in self.unique_api_keys()]

    @property
    def total(self):
        return self.unique_api_keys().count()

    def unique_api_keys(self):
        usernames = self.account.get_web_user_usernames()
        user_ids = User.objects.filter(username__in=usernames).values_list('id', flat=True)
        domains = self.account.get_domains()

        return HQApiKey.objects.filter(
            user_id__in=Subquery(user_ids),
            is_active=True
        ).filter(
            Q(domain__in=domains) | Q(domain='')
        )

    def _get_api_key_row(self, api_key):
        if api_key.domain:
            scope = api_key.domain
        else:
            user_domains = set(WebUser.get_by_username(api_key.user.username).get_domains())
            account_domains = set(self.account.get_domains())
            intersected_domains = user_domains.intersection(account_domains)
            scope = ', '.join((intersected_domains))

        return [
            api_key.user.username,
            api_key.name,
            scope,
            self.format_date(api_key.expiration_date),
            self.format_date(api_key.created),
            self.format_date(api_key.last_used),
        ]


class Enterprise2FAReport(EnterpriseReport):
    title = gettext_lazy('Two Factor Authentication')
    total_description = gettext_lazy('# of Project Spaces without 2FA')

    @property
    def headers(self):
        return [_('Project Space without 2FA'),]

    def total_for_domain(self, domain_obj):
        if domain_obj.two_factor_auth:
            return 0
        return 1

    def rows_for_domain(self, domain_obj):
        if domain_obj.two_factor_auth:
            return []
        return [(domain_obj.name,)]


class EnterpriseAppVersionComplianceReport(EnterpriseReport):
    title = gettext_lazy('Application Version Compliance')
    total_description = gettext_lazy('% of Applications Up to Date Across All Mobile Workers')

    def __init__(self, account, couch_user):
        super().__init__(account, couch_user)
        self.builds_by_app_id = {}
        self.build_info_cache = {}

    @property
    def headers(self):
        return [
            _('Mobile Worker'),
            _('Project Space'),
            _('Application'),
            _('Latest Version Available When Last Used'),
            _('Version in Use'),
            _('Last Used [UTC]'),
        ]

    @property
    def rows(self):
        rows = []
        for domain in self.account.get_domains():
            rows.extend(self.rows_for_domain(domain))
        return rows

    @property
    def total(self):
        return '--'

    def rows_for_domain(self, domain):
        rows = []
        app_name_by_id = {}
        app_ids = get_app_ids_in_domain(domain)

        for row_data in self._get_user_builds(domain, app_ids):
            version_in_use = str(row_data['build']['build_version'])
            latest_version = str(row_data['latest_version'])
            if is_out_of_date(version_in_use, latest_version):
                app_id = row_data['build']['app_id']
                if app_id not in app_name_by_id:
                    app_name_by_id[app_id] = Application.get_db().get(app_id).get('name')
                rows.append([
                    row_data['username'],
                    domain,
                    app_name_by_id[app_id],
                    latest_version,
                    version_in_use,
                    self.format_date(DateTimeProperty.deserialize(row_data['build']['build_version_date'])),
                ])

        return rows

    def _get_user_builds(self, domain, app_ids):
        user_query = (UserES()
            .domain(domain)
            .mobile_users()
            .source([
                'username',
                'reporting_metadata.last_builds',
            ]))
        for user in user_query.run().hits:
            last_builds = user.get('reporting_metadata', {}).get('last_builds', [])
            for build in last_builds:
                app_id = build.get('app_id')
                build_version = build.get('build_version')
                if app_id not in app_ids or not build_version:
                    continue
                build_version_date = DateTimeProperty.deserialize(build.get('build_version_date'))
                latest_version = self.get_latest_build_version(domain, app_id, build_version_date)
                yield {
                    'username': user['username'],
                    'build': build,
                    'latest_version': latest_version,
                }

    def get_latest_build_version(self, domain, app_id, at_datetime):
        builds = self.get_app_builds(domain, app_id)
        latest_build = self._find_latest_build_version_from_builds(builds, at_datetime)

        return latest_build

    def get_app_builds(self, domain, app_id):
        if app_id not in self.builds_by_app_id:
            app_es = (
                AppES()
                .domain(domain)
                .is_build()
                .app_id(app_id)
                .sort('version', desc=True)
                .is_released()
                .source(['_id', 'version', 'last_released', 'built_on'])
            )
            self.builds_by_app_id[app_id] = app_es.run().hits
        return self.builds_by_app_id[app_id]

    def _find_latest_build_version_from_builds(self, all_builds, at_datetime):
        for build_doc in all_builds:
            build_id = build_doc['_id']
            build_info = self.build_info_cache.get(build_id)
            if not build_info:
                # last_released is added in 2019, build before 2019 don't have this field
                # TODO: have a migration to populate last_released from built_on
                # Then this code can be modified to use last_released only
                released_date = build_doc['last_released'] or build_doc['built_on']
                build_info = {
                    'version': build_doc['version'],
                    'last_released': DateTimeProperty.deserialize(released_date)
                }
                self.build_info_cache[build_id] = build_info

            if build_info['last_released'] <= at_datetime:
                return build_info['version']
        return None


def _format_percentage_for_enterprise_tile(dividend, divisor):
    if not divisor:
        return '--'
    return f"{dividend / divisor * 100:.1f}%"
