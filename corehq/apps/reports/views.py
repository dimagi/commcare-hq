import copy
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cmp_to_key, wraps

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop
from django.views.decorators.http import (
    require_GET,
    require_http_methods,
    require_POST,
)
from django.views.generic import View
from django.views.generic.base import TemplateView
from django.views.generic.edit import ModelFormMixin, ProcessFormView

import langcodes
import pytz
from couchdbkit.exceptions import ResourceNotFound
from django_prbac.utils import has_privilege
from memoized import memoized
from no_exceptions.exceptions import Http403
from django_prbac.decorators import requires_privilege

from casexml.apps.case import const
from casexml.apps.case.templatetags.case_tags import case_inline_display
from casexml.apps.case.xform import extract_case_blocks, get_case_updates
from couchexport.export import Format
from dimagi.utils.decorators.datespan import datespan_in_request
from dimagi.utils.parsing import json_format_datetime
from dimagi.utils.web import json_response

from corehq.apps.app_manager.util import get_form_source_download_url
from corehq.apps.cloudcare import CLOUDCARE_DEVICE_ID
from corehq.apps.domain.decorators import (
    api_auth,
    login_and_domain_required,
    require_superuser,
)
from corehq.apps.domain.models import Domain, DomainAuditRecordEntry
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.groups.models import Group
from corehq.apps.hqwebapp.decorators import (
    use_datatables,
    use_daterangepicker,
    use_jquery_ui,
    use_multiselect,
)
from corehq.apps.hqwebapp.doc_info import DocInfo, get_doc_info_by_id
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_enabled
from corehq.apps.hqwebapp.templatetags.proptable_tags import (
    DisplayConfig,
    get_display_data,
)
from corehq.apps.hqwebapp.view_permissions import user_can_view_reports
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.apps.locations.permissions import (
    can_edit_form_location,
    conditionally_location_safe,
    location_restricted_exception,
    location_safe,
    report_class_is_location_safe,
)
from corehq.apps.receiverwrapper.auth import AuthContext
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.reports.formdetails.readable import (
    get_data_cleaning_data,
    get_readable_data_for_submission,
)
from corehq.apps.reports.models import QueryStringHash, TableauConnectedApp
from corehq.apps.reports.util import get_all_tableau_groups, TableauAPIError
from corehq.apps.saved_reports.models import ReportConfig, ReportNotification
from corehq.apps.saved_reports.tasks import (
    send_delayed_report,
    send_email_report,
)
from corehq.apps.userreports.util import \
    default_language as ucr_default_language
from corehq.apps.users.dbaccessors import get_all_user_rows
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import (
    CommCareUser,
    HqPermissions,
    WebUser,
)
from corehq.apps.users.permissions import (
    CASE_EXPORT_PERMISSION,
    DEID_EXPORT_PERMISSION,
    FORM_EXPORT_PERMISSION,
)
from corehq.blobs import CODES, NotFound, get_blob_db, models
from corehq.form_processor.exceptions import AttachmentNotFound, CaseNotFound
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.form_processor.utils.xform import resave_form
from corehq.motech.generic_inbound.utils import revert_api_request_from_form
from corehq.tabs.tabclasses import ProjectReportsTab
from corehq.toggles import VIEW_FORM_ATTACHMENT, TABLEAU_USER_SYNCING
from corehq.util import cmp
from corehq.util.couch import get_document_or_404
from corehq.util.download import get_download_response
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import (
    get_timezone_for_request,
    get_timezone_for_user,
)
from corehq.util.view_utils import get_form_or_404, request_as_dict, reverse
from corehq import privileges, toggles

from .dispatcher import ProjectReportDispatcher
from .forms import (
    SavedReportConfigForm,
    TableauServerForm,
    TableauVisualizationForm,
    UpdateTableauVisualizationForm,
)
from .lookup import ReportLookup, get_full_report_name
from .models import TableauVisualization
from .standard import ProjectReport, inspect

DATE_FORMAT = "%Y-%m-%d %H:%M"

datespan_default = datespan_in_request(
    from_param="startdate",
    to_param="enddate",
    default_days=7,
)

require_form_export_permission = require_permission(
    HqPermissions.view_report, FORM_EXPORT_PERMISSION, login_decorator=None)
require_form_deid_export_permission = require_permission(
    HqPermissions.view_report, DEID_EXPORT_PERMISSION, login_decorator=None)
require_case_export_permission = require_permission(
    HqPermissions.view_report, CASE_EXPORT_PERMISSION, login_decorator=None)

require_form_view_permission = require_permission(
    HqPermissions.view_report,
    'corehq.apps.reports.standard.inspect.SubmitHistory',
    login_decorator=None,
)

require_can_view_all_reports = require_permission(HqPermissions.view_reports)


def _can_view_form_attachment():
    def decorator(view_func):
        @wraps(view_func)
        def _inner(request, domain, *args, **kwargs):
            if VIEW_FORM_ATTACHMENT.enabled(domain):
                return view_func(request, domain, *args, **kwargs)
            try:
                response = require_form_view_permission(view_func)(request, domain, *args, **kwargs)
            except PermissionDenied:
                response = HttpResponseForbidden()
            return response

        return api_auth()(_inner)
    return decorator


can_view_form_attachment = _can_view_form_attachment()


def location_restricted_scheduled_reports_enabled(request, *args, **kwargs):
    return toggles.LOCATION_RESTRICTED_SCHEDULED_REPORTS.enabled(kwargs.get('domain'))


@login_and_domain_required
@conditionally_location_safe(location_restricted_scheduled_reports_enabled)
def reports_home(request, domain):
    if user_can_view_reports(request.project, request.couch_user):
        return HttpResponseRedirect(reverse(MySavedReportsView.urlname, args=[domain]))

    if toggles.EMBEDDED_TABLEAU.enabled_for_request(request):
        from .standard.tableau import TableauView
        for viz in TableauVisualization.for_user(domain, request.couch_user):
            return HttpResponseRedirect(reverse(TableauView.urlname, args=[domain, viz.id]))

    raise Http404()


class BaseProjectReportSectionView(BaseDomainView):
    section_name = gettext_lazy("Project Reports")

    def dispatch(self, request, *args, **kwargs):
        request.project = Domain.get_by_name(self.domain)
        if not hasattr(request, 'couch_user'):
            raise Http404()
        if not user_can_view_reports(request.project, request.couch_user):
            raise Http404()
        return super(BaseProjectReportSectionView, self).dispatch(request, *args, **kwargs)

    @property
    def section_url(self):
        return reverse('reports_home', args=(self.domain, ))


@conditionally_location_safe(location_restricted_scheduled_reports_enabled)
class MySavedReportsView(BaseProjectReportSectionView):
    urlname = 'saved_reports'
    page_title = gettext_noop("My Saved Reports")
    template_name = 'reports/reports_home.html'

    @use_jquery_ui
    @use_datatables
    @use_daterangepicker
    def dispatch(self, request, *args, **kwargs):
        return super(MySavedReportsView, self).dispatch(request, *args, **kwargs)

    @property
    def language(self):
        return self.request.couch_user.language or ucr_default_language()

    @property
    def good_configs(self):
        all_configs = ReportConfig.by_domain_and_owner(self.domain, self.request.couch_user._id, stale=False)
        good_configs = []
        for config in all_configs:
            if config.is_configurable_report and not config.configurable_report:
                continue

            good_configs.append(config.to_complete_json(lang=self.language))
        return good_configs

    @property
    def scheduled_reports(self):

        def _is_valid(rn):
            # the _id check is for weird bugs we've seen in the wild that look like
            # oddities in couch.
            return (
                hasattr(rn, "_id")
                and rn._id
                and rn.configs
                and (
                    not hasattr(rn, 'report_slug')
                    or rn.report_slug != 'admin_domains'
                )
            )

        scheduled_reports = [
            r for r in ReportNotification.by_domain_and_owner(
                self.domain, self.request.couch_user._id)
            if _is_valid(r)
        ]
        scheduled_reports = sorted(scheduled_reports,
                                   key=lambda s: s.configs[0].name)
        for report in scheduled_reports:
            soft_shift_to_domain_timezone(report)
        return sorted(scheduled_reports, key=self._report_sort_key())

    @property
    def others_scheduled_reports(self):
        def _is_valid(rn):
            # the _id check is for weird bugs we've seen in the wild that look like
            # oddities in couch.
            return (
                hasattr(rn, "_id")
                and rn._id
                and rn.configs
                and (
                    not hasattr(rn, 'report_slug')
                    or rn.report_slug != 'admin_domains'
                )
            )

        ret = []
        key = [self.domain]
        all_scheduled_reports = ReportNotification.view('reportconfig/user_notifications', reduce=False,
                                                        include_docs=True, startkey=key, endkey=key + [{}])
        user = self.request.couch_user
        owner_id = user.username if user.is_web_user() else user.get_email()
        for scheduled_report in all_scheduled_reports:
            if not _is_valid(scheduled_report) or owner_id == scheduled_report.owner_email:
                continue
            soft_shift_to_domain_timezone(scheduled_report)
            if scheduled_report.can_be_viewed_by(user):
                ret.append(scheduled_report)
        return sorted(ret, key=self._report_sort_key())

    @property
    def shared_saved_reports(self):
        user = self.request.couch_user
        config_reports = []

        if user.is_domain_admin(self.domain):
            # Admin user should see ALL shared saved reports
            config_reports = ReportConfig.shared_on_domain(self.domain)
        else:
            # The non-admin user should ONLY see their saved reports (ie ReportConfigs) which have been used
            # in a ReportNotification (not other users' ReportConfigs).
            [config_reports.extend(r.configs) for r in self.scheduled_reports]

        good_configs = [
            config.to_complete_json(lang=self.language)
            for config in config_reports
            if not (config.is_configurable_report and not config.configurable_report)
        ]
        return good_configs

    def _report_sort_key(self):
        return lambda report: report.configs[0].full_name.lower() if report.configs else None

    @property
    def page_context(self):
        user = self.request.couch_user
        others_scheduled_reports = self.others_scheduled_reports

        class OthersScheduledReportWrapper(ReportNotification):
            @property
            def context_secret(self):
                return self.get_secret(user.get_email())

        for other_report in others_scheduled_reports:
            other_report.__class__ = OthersScheduledReportWrapper

        others_scheduled_reports = [
            self.report_details(r, user.get_email(), r.context_secret) for r in others_scheduled_reports
        ]

        scheduled_reports = [
            self.report_details(r) for r in self.scheduled_reports
        ]

        return {
            'couch_user': user,
            'user_email': user.get_email(),
            'is_admin': user.is_domain_admin(self.domain),
            'configs': self.good_configs,
            'scheduled_reports': scheduled_reports,
            'others_scheduled_reports': others_scheduled_reports,
            'shared_saved_reports': self.shared_saved_reports,
            'report': {
                'title': self.page_title,
                'show': True,
                'slug': None,
                'is_async': True,
                'section_name': self.section_name,
            }
        }

    @staticmethod
    def report_details(report, user_email=None, context_secret=None):
        details = {
            'id': report.get_id,
            'addedToBulk': report.addedToBulk,
            'domain': report.domain,
            'owner_id': report.owner_id,
            'recipient_emails': report.recipient_emails,
            'config_ids': report.config_ids,
            'send_to_owner': report.send_to_owner,
            'hour': report.hour if report.interval != 'hourly' else None,
            'minute': report.minute,
            'day': report.day,
            'uuid': report.uuid,
            'start_date': report.start_date,

            #property methods
            'configs': [{'url': r.url,
                         'name': r.name,
                         'report_name': r.report_name} for r in report.configs],
            'is_editable': report.is_editable,
            'owner_email': report.owner_email,
            'day_name': report.day_name,

            #urls
            'editUrl': reverse(ScheduledReportsView.urlname, args=(report.domain, report.get_id)),
            'viewUrl': reverse(view_scheduled_report, args=(report.domain, report.get_id)),
            'sendUrl': reverse(send_test_scheduled_report, args=(report.domain, report.get_id)),
            'deleteUrl': reverse(delete_scheduled_report, args=(report.domain, report.get_id)),
        }

        #only for others_scheduled_reports
        if user_email and context_secret:
            details['unsubscribeUrl'] = reverse(ReportNotificationUnsubscribeView.urlname,
                                                args=(report.get_id, user_email, context_secret))
        else:
            details['unsubscribeUrl'] = ''

        return details


def should_update_export(last_accessed):
    cutoff = datetime.utcnow() - timedelta(days=settings.SAVED_EXPORT_ACCESS_CUTOFF)
    return not last_accessed or last_accessed < cutoff


def touch_saved_reports_views(user, domain):
    """
    Hit the saved reports views so stale=update_after doesn't cause the user to
    see old or deleted data after a change when they next load the reports
    homepage.

    """
    ReportConfig.by_domain_and_owner(domain, user._id, limit=1, stale=False)
    ReportNotification.by_domain_and_owner(domain, user._id, limit=1, stale=False)


@location_safe
class AddSavedReportConfigView(View):
    name = 'add_report_config'

    @method_decorator(login_and_domain_required)
    def post(self, request, domain, *args, **kwargs):
        self.domain = domain

        if not self.saved_report_config_form.is_valid():
            errors = self.saved_report_config_form.errors.get('__all__', [])
            return HttpResponseBadRequest(', '.join(errors))

        update_config_data = copy.copy(self.saved_report_config_form.cleaned_data)
        del update_config_data['_id']
        update_config_data.update({
            'filters': self.filters,
        })
        for field in self.config.properties().keys():
            if field in update_config_data:
                setattr(self.config, field, update_config_data[field])

        # remove start and end date if the date range is "last xx days" or none
        if self.saved_report_config_form.cleaned_data['date_range'] in [
            'last30',
            'last7',
            'lastn',
            'lastmonth',
            'lastyear',
            None,
        ]:
            if "start_date" in self.config:
                delattr(self.config, "start_date")
            if "end_date" in self.config:
                delattr(self.config, "end_date")
        # remove days if the date range has specific dates
        elif self.saved_report_config_form.cleaned_data['date_range'] in [
            'since',
            'range',
        ]:
            if "days" in self.config:
                delattr(self.config, "days")

        self.config.save()
        ProjectReportsTab.clear_dropdown_cache(self.domain, request.couch_user)
        ReportConfig.shared_on_domain.clear(ReportConfig, domain)

        touch_saved_reports_views(request.couch_user, self.domain)

        return json_response(self.config)

    @property
    @memoized
    def config(self):
        _id = self.saved_report_config_form.cleaned_data['_id']
        if not _id:
            _id = None  # make sure we pass None not a blank string
        config = ReportConfig.get_or_create(_id)
        if config.owner_id:
            # in case a non-admin user maliciously tries to edit another user's config
            # or an admin edits a non-shared report in some way
            assert config.owner_id == self.user_id or (
                self.user.is_domain_admin(self.domain) and config.is_shared_on_domain()
            )
        else:
            config.domain = self.domain
            config.owner_id = self.user_id
        return config

    @property
    @memoized
    def saved_report_config_form(self):
        return SavedReportConfigForm(
            self.domain,
            self.user_id,
            self.post_data
        )

    @property
    def filters(self):
        filters = copy.copy(self.post_data.get('filters', {}))
        for field in ['startdate', 'enddate']:
            if field in filters:
                del filters[field]
        return filters

    @property
    def post_data(self):
        return json.loads(self.request.body.decode('utf-8'))

    @property
    def user_id(self):
        return self.user._id

    @property
    def user(self):
        return self.request.couch_user


def _querydict_to_dict(query_dict):
    data = {}
    for key in query_dict.keys():
        if key.endswith('[]'):
            v = query_dict.getlist(key)
            key = key[:-2]  # slice off the array naming
        else:
            v = query_dict[key]
        data[key] = v
    return data


@dataclass
class Timezone:
    hours: int
    minutes: int

    def __str__(self):
        return f"{self.hours:+03}:{self.minutes:02}"


@login_and_domain_required
@datespan_default
@require_POST
def email_report(request, domain, report_slug, dispatcher_class=ProjectReportDispatcher, once=False):
    from .forms import EmailReportForm

    form = EmailReportForm(_querydict_to_dict(request.POST))
    if not form.is_valid():
        return HttpResponseBadRequest(json.dumps(form.get_readable_errors()))

    if not _can_email_report(report_slug, request, dispatcher_class, domain):
        raise Http404()

    recipient_emails = set(form.cleaned_data['recipient_emails'] or [])

    if form.cleaned_data['send_to_owner']:
        recipient_emails.add(request.couch_user.get_email())

    request_data = request_as_dict(request)

    report_type = dispatcher_class.prefix
    send_email_report.delay(recipient_emails, domain, report_slug, report_type,
                            request_data, once, form.cleaned_data)
    return HttpResponse()


def _can_email_report(report_slug, request, dispatcher_class, domain):
    dispatcher = dispatcher_class()
    lookup = ReportLookup(dispatcher.map_name)
    report = lookup.get_report(domain, report_slug)
    if not report:
        return False

    report_name = get_full_report_name(report)
    return dispatcher.permissions_check(report_name, request, domain)


@login_and_domain_required
@require_http_methods(['DELETE'])
@conditionally_location_safe(location_restricted_scheduled_reports_enabled)
def delete_config(request, domain, config_id):
    ReportConfig.shared_on_domain.clear(ReportConfig, domain)

    try:
        saved_report = ReportConfig.get(config_id)
    except ResourceNotFound:
        raise Http404()

    if not _can_delete_saved_report(saved_report, request.couch_user, domain):
        raise Http404()

    saved_report.delete()
    ProjectReportsTab.clear_dropdown_cache(domain, request.couch_user)

    touch_saved_reports_views(request.couch_user, domain)
    return HttpResponse()


def _can_delete_saved_report(report, user, domain):
    return domain == report.domain and user._id == report.owner_id or (
        user.is_domain_admin(domain) and report.is_shared_on_domain()
    )


def normalize_hour(hour):
    day_change = 0
    if hour < 0:
        day_change = -1
        hour += 24
    elif hour >= 24:
        day_change = 1
        hour -= 24

    assert 0 <= hour < 24
    return (hour, day_change)


def calculate_hour(hour, hour_difference, minute_difference):
    hour -= hour_difference
    if hour_difference > 0 and minute_difference != 0:
        hour -= 1
    return normalize_hour(hour)


def recalculate_hour(hour, hour_difference, minute_difference):
    hour += hour_difference
    if hour_difference > 0 and minute_difference != 0:
        hour += 1
    return normalize_hour(hour)


def get_timezone_difference(domain):
    domain_obj = Domain.get_by_name(domain)
    tz_diff = datetime.now(pytz.timezone(domain_obj.default_timezone)).strftime('%z')
    return Timezone(int(tz_diff[:3]), int(tz_diff[3:]))


def calculate_day(interval, day, day_change):
    if interval == "weekly":
        return (day + day_change) % 7
    elif interval == "monthly":
        return (day - 1 + day_change) % 31 + 1
    return day


def _update_instance_time_with_func(report_notification, time_func, minute=None):
    time_difference = get_timezone_difference(report_notification.domain)
    (report_notification.hour, day_change) = time_func(
        report_notification.hour,
        time_difference.hours,
        time_difference.minutes
    )

    if minute is None:
        report_notification.minute = time_difference.minutes
    else:
        report_notification.minute = minute

    if day_change:
        report_notification.day = calculate_day(report_notification.interval, report_notification.day, day_change)

    if report_notification.interval == "hourly":
        (report_notification.stop_hour, _) = time_func(
            report_notification.stop_hour, time_difference.hours, time_difference.minutes
        )
        report_notification.stop_minute = time_difference.minutes


def soft_shift_to_domain_timezone(report_notification):
    _update_instance_time_with_func(
        report_notification,
        recalculate_hour,
        minute=0,
    )


def soft_shift_to_server_timezone(report_notification):
    _update_instance_time_with_func(
        report_notification,
        calculate_hour,
    )


@conditionally_location_safe(location_restricted_scheduled_reports_enabled)
class ScheduledReportsView(BaseProjectReportSectionView):
    urlname = 'edit_scheduled_report'
    page_title = _("Scheduled Report")
    template_name = 'reports/bootstrap3/edit_scheduled_report.html'

    @method_decorator(require_permission(HqPermissions.download_reports))
    @use_multiselect
    @use_jquery_ui
    def dispatch(self, request, *args, **kwargs):
        return super(ScheduledReportsView, self).dispatch(request, *args, **kwargs)

    @property
    def scheduled_report_id(self):
        return self.kwargs.get('scheduled_report_id')

    def can_edit_report(self, report_instance):
        owner = report_instance.owner
        owner_domain = report_instance.domain
        current_user = self.request.couch_user
        return current_user.user_id == owner.user_id or current_user.is_domain_admin(owner_domain)

    @property
    @memoized
    def report_notification(self):
        if self.scheduled_report_id:
            instance = ReportNotification.get(self.scheduled_report_id)
            soft_shift_to_domain_timezone(instance)

            if not self.can_edit_report(instance):
                raise Http403()
        else:
            instance = ReportNotification(
                owner_id=self.request.couch_user._id,
                domain=self.domain,
                config_ids=[],
                hour=8,
                minute=0,
                stop_hour=20,
                stop_minute=0,
                send_to_owner=True,
                recipient_emails=[],
                language=None,
            )
        return instance

    @property
    def is_new(self):
        """True if before this request the ReportNotification object did not exist"""
        return bool(not self.scheduled_report_id)

    @property
    def page_name(self):
        if not self.configs:
            return self.page_title
        if self.is_new:
            return _("New Scheduled Report")
        return _("Edit Scheduled Report")

    @property
    def owner_id(self):
        if self.scheduled_report_id:
            return ReportNotification.get(self.scheduled_report_id).owner_id
        else:
            return None

    @property
    @memoized
    def configs(self):
        user = self.request.couch_user

        if self.scheduled_report_id and user.is_domain_admin(self.domain):
            return self.report_notification.configs

        report_configurations = ReportConfig.by_domain_and_owner(
            self.domain,
            user._id,
            include_shared=user.is_domain_admin(self.domain)
        )

        return [
            c for c in report_configurations
            if c.report and c.report.emailable
        ]

    @property
    def config_choices(self):
        config_choices = [(c._id, c.full_name) for c in self.configs]

        def _sort_key(config_choice):
            config_choice_id = config_choice[0]
            if config_choice_id in self.report_notification.config_ids:
                return self.report_notification.config_ids.index(config_choice_id)
            else:
                return len(self.report_notification.config_ids)

        return sorted(config_choices, key=_sort_key)

    @property
    @memoized
    def scheduled_report_form(self):
        initial = self.report_notification.to_json()

        kwargs = {'initial': initial}
        if self.request.method == "POST":
            args = (self.request.POST, )
            selected_emails = self.request.POST.getlist('recipient_emails', {})
        else:
            args = ()
            selected_emails = kwargs.get('initial', {}).get('recipient_emails', [])

        web_user_emails = [
            WebUser.wrap(row['doc']).get_email()
            for row in get_all_user_rows(self.domain, include_web_users=True,
                                         include_mobile_users=False, include_docs=True)
        ]
        for email in selected_emails:
            if email not in web_user_emails:
                web_user_emails = [email] + web_user_emails

        from corehq.apps.reports.forms import ScheduledReportForm
        form = ScheduledReportForm(*args, **kwargs)
        form.fields['config_ids'].choices = self.config_choices
        form.fields['recipient_emails'].choices = [(e, e) for e in web_user_emails]

        form.fields['hour'].help_text = _("This scheduled report's timezone is %s (UTC%s)") % \
                                         (Domain.get_by_name(self.domain)['default_timezone'],
                                          get_timezone_difference(self.domain))
        form.fields['stop_hour'].help_text = _("This scheduled report's timezone is %s (UTC%s)") % \
                                              (Domain.get_by_name(self.domain)['default_timezone'],
                                               get_timezone_difference(self.domain))
        return form

    @property
    def page_context(self):
        context = {
            'form': None,
            'report': {
                'show': user_can_view_reports(self.request.project, self.request.couch_user),
                'slug': None,
                'default_url': reverse('reports_home', args=(self.domain,)) + '#scheduled-reports',
                'is_async': False,
                'section_name': ProjectReport.section_name,
                'title': self.page_name,
            }
        }

        if not self.configs and not self.request.couch_user.is_domain_admin(self.domain):
            return context

        is_configurable_map = {c._id: c.is_configurable_report for c in self.configs}
        supports_translations = {c._id: c.supports_translations for c in self.configs}
        languages_map = {c._id: list(c.languages | set(['en'])) for c in self.configs}
        languages_for_select = {tup[0]: tup for tup in langcodes.get_all_langs_for_select()}

        context.update({
            'form': self.scheduled_report_form,
            'day_value': getattr(self.report_notification, "day", 1),
            'weekly_day_options': ReportNotification.day_choices(),
            'monthly_day_options': [(i, i) for i in range(1, 32)],
            'form_action': _("Create a new") if self.is_new else _("Edit"),
            'is_configurable_map': is_configurable_map,
            'supports_translations': supports_translations,
            'languages_map': languages_map,
            'languages_for_select': languages_for_select,
            'is_owner': self.is_new or self.request.couch_user._id == self.owner_id,
        })
        return context

    def post(self, request, *args, **kwargs):
        if self.scheduled_report_form.is_valid():
            try:
                self.report_notification.update_attributes(list(self.scheduled_report_form.cleaned_data.items()))
            except ValidationError as err:
                kwargs['error'] = str(err)
                messages.error(request, gettext_lazy(kwargs['error']))
                return self.get(request, *args, **kwargs)

            soft_shift_to_server_timezone(self.report_notification)
            self.report_notification.save()

            ProjectReportsTab.clear_dropdown_cache(self.domain, self.request.couch_user)
            ReportConfig.shared_on_domain.clear(ReportConfig, self.domain)
            if self.is_new:
                DomainAuditRecordEntry.update_calculations(self.domain, 'cp_n_saved_scheduled_reports')
                messages.success(request, _("Scheduled report added."))
            else:
                messages.success(request, _("Scheduled report updated."))

            touch_saved_reports_views(request.couch_user, self.domain)
            return HttpResponseRedirect(reverse('reports_home', args=(self.domain,)) + '#scheduled-reports')

        return self.get(request, *args, **kwargs)


class ReportNotificationUnsubscribeView(TemplateView):
    template_name = 'reports/notification_unsubscribe.html'
    urlname = 'notification_unsubscribe'
    not_found_error = gettext_noop('Could not find the requested Scheduled Report')
    broken_link_error = gettext_noop('Invalid unsubscribe link')
    report = None

    def get(self, request, *args, **kwargs):
        if 'success' not in kwargs and 'error' not in kwargs:
            try:
                self.report = ReportNotification.get(kwargs.pop('scheduled_report_id'))
                email = kwargs.pop('user_email')

                if kwargs.pop('scheduled_report_secret') != self.report.get_secret(email):
                    raise ValidationError(self.broken_link_error)
                if email not in self.report.all_recipient_emails:
                    raise ValidationError(gettext_noop('This email address has already been unsubscribed.'))
            except ResourceNotFound:
                kwargs['error'] = self.not_found_error
            except ValidationError as err:
                kwargs['error'] = err.message

        if 'error' in kwargs:
            messages.error(request, gettext_lazy(kwargs['error']))
        elif 'success' in kwargs:
            messages.success(request, gettext_lazy(kwargs['success']))

        return super(ReportNotificationUnsubscribeView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ReportNotificationUnsubscribeView, self).get_context_data(**kwargs)
        context.update({'report': self.report})
        return context

    def post(self, request, *args, **kwargs):
        try:
            self.report = ReportNotification.get(kwargs.pop('scheduled_report_id'))
            email = kwargs.pop('user_email')

            if kwargs.pop('scheduled_report_secret') != self.report.get_secret(email):
                raise ValidationError(self.broken_link_error)

            self.report.remove_recipient(email)

            if len(self.report.recipient_emails) > 0 or self.report.send_to_owner:
                self.report.save()
            else:
                self.report.delete()

            kwargs['success'] = gettext_noop('Successfully unsubscribed from report notification.')
        except ResourceNotFound:
            kwargs['error'] = self.not_found_error
        except ValidationError as err:
            kwargs['error'] = err.message

        return self.get(request, *args, **kwargs)


@login_and_domain_required
@require_POST
@conditionally_location_safe(location_restricted_scheduled_reports_enabled)
def delete_scheduled_report(request, domain, scheduled_report_id):
    user = request.couch_user
    delete_count = request.POST.get("bulkDeleteCount")

    try:
        if delete_count:
            delete_list = json.loads(request.POST.get("deleteList"))
            scheduled_reports = [ReportNotification.get(report_id) for report_id in delete_list]
        else:
            scheduled_report = ReportNotification.get(scheduled_report_id)
    except ResourceNotFound:
        # was probably already deleted by a fast-clicker.
        pass
    else:
        ReportConfig.shared_on_domain.clear(ReportConfig, domain)

        if delete_count:
            for report in scheduled_reports:
                if not _can_delete_scheduled_report(report, user, domain):
                    raise Http404()

            for report in scheduled_reports:
                report.delete()
            if int(delete_count) > 1:
                plural = "s were"
            else:
                plural = " was"
            messages.success(
                request,
                format_html(_("<strong>{}</strong> Scheduled report{} deleted!"), delete_count, plural)
            )
            # not necessary since it just refreshes from the js
            return HttpResponse(reverse("reports_home", args=(domain,)) + '#scheduled-reports')
        else:
            if not _can_delete_scheduled_report(scheduled_report, user, domain):
                raise Http404()

            scheduled_report.delete()
            messages.success(request, "Scheduled report deleted!")

    return HttpResponseRedirect(reverse("reports_home", args=(domain,)) + '#scheduled-reports')


def _can_delete_scheduled_report(report, user, domain):
    if report.domain != domain:
        return False

    return user._id == report.owner_id or user.is_domain_admin(domain)


@login_and_domain_required
@conditionally_location_safe(location_restricted_scheduled_reports_enabled)
def send_test_scheduled_report(request, domain, scheduled_report_id):
    if not _can_send_test_report(scheduled_report_id, request.couch_user, domain):
        raise Http404()
    send_count = request.POST.get("bulkSendCount")

    try:
        if send_count:
            for report_id in json.loads(request.POST.get("sendList")):
                send_delayed_report(report_id)
        else:
            send_delayed_report(scheduled_report_id)
    except Exception as e:
        import logging
        logging.exception(e)
        messages.error(request, _("An error occurred, message unable to send"))
    else:
        if send_count and int(send_count) > 1:
            messages.success(
                request,
                format_html(_("{} reports sent to their recipients"), send_count)
            )
        else:
            messages.success(request, _("Report sent to this report's recipients"))

    if send_count:
        return HttpResponse(reverse("reports_home", args=(domain,)) + '#scheduled-reports')
    else:
        return HttpResponseRedirect(reverse("reports_home", args=(domain,)) + '#scheduled-reports')


def _can_send_test_report(report_id, user, domain):
    try:
        report = ReportNotification.get(report_id)
    except ResourceNotFound:
        return False

    if report.domain != domain:
        return False

    return user._id == report.owner._id or user.is_domain_admin(domain)


def get_scheduled_report_response(couch_user, domain, scheduled_report_id,
                                  email=True, attach_excel=False,
                                  send_only_active=False, request=None):
    """
    This function somewhat confusingly returns a tuple of: (response, excel_files)
    If attach_excel is false, excel_files will always be an empty list.
    If send_only_active is True, then only ReportConfigs that have a start_date
    in the past will be sent. If none of the ReportConfigs are valid, no email will
    be sent.
    """
    # todo: clean up this API?
    domain_obj = Domain.get_by_name(domain)
    if not user_can_view_reports(domain_obj, couch_user):
        raise Http404

    scheduled_report = ReportNotification.get_report(scheduled_report_id)
    if not scheduled_report:
        raise Http404

    if not (scheduled_report.domain == domain and scheduled_report.can_be_viewed_by(couch_user)):
        raise Http404

    from django.http import HttpRequest
    if not request:
        request = HttpRequest()
        request.couch_user = couch_user
        request.user = couch_user.get_django_user()
        request.domain = domain
        request.couch_user.current_domain = domain

    return _render_report_configs(
        request,
        scheduled_report.configs,
        scheduled_report.domain,
        scheduled_report.owner_id,
        couch_user,
        email,
        attach_excel=attach_excel,
        lang=scheduled_report.language,
        send_only_active=send_only_active,
    )


def _render_report_configs(request, configs, domain, owner_id, couch_user, email,
                           notes=None, attach_excel=False, once=False, lang=None,
                           send_only_active=False):
    """
    Renders only notification's main content, which then may be used to generate full notification body.

    :returns: two-tuple `(report_text: str, excel_files: list)`. Both
    values are empty when there are no applicable report configs.
    `excel_files` is a list of dicts.
    """
    from dimagi.utils.web import get_url_base

    report_outputs = []
    excel_attachments = []
    format = Format.from_format(request.GET.get('format') or Format.XLS_2007)

    # Show only the report configs that have started their reporting period
    if send_only_active:
        configs = [c for c in configs if c.is_active]

    # Don't send an email if none of the reports configs have started
    if len(configs) == 0:
        return "", []

    for config in configs:
        content, excel_file = config.get_report_content(lang,
                                                        attach_excel=attach_excel,
                                                        couch_user=couch_user,
                                                        subreport_slug=config.subreport_slug)
        if excel_file:
            excel_attachments.append({
                'title': config.full_name + "." + format.extension,
                'file_obj': excel_file,
                'mimetype': format.mimetype
            })
        date_range = config.get_date_range()
        report_outputs.append({
            'title': config.full_name,
            'url': config.url,
            'content': content,
            'is_active': config.is_active,
            'description': config.description,
            "startdate": date_range.get("startdate") if date_range else "",
            "enddate": date_range.get("enddate") if date_range else "",
        })

    response = render(request, "reports/report_email_content.html", {
        "reports": report_outputs,
        "domain": domain,
        "couch_user": owner_id,
        "DNS_name": get_url_base(),
        "owner_name": couch_user.full_name or couch_user.get_email(),
        "email": email,
        "notes": notes,
        "report_type": _("once off report") if once else _("scheduled report"),
    })
    return response.content.decode("utf-8"), excel_attachments


def render_full_report_notification(request, content, email=None, report_notification=None):
    """
    Renders full notification body with provided main content.
    """
    from django.http import HttpRequest

    from dimagi.utils.web import get_url_base

    if request is None:
        request = HttpRequest()

    unsub_link = None
    if report_notification and email:
        unsub_link = get_url_base() + reverse('notification_unsubscribe', kwargs={
            'scheduled_report_id': report_notification._id,
            'user_email': email,
            'scheduled_report_secret': report_notification.get_secret(email)
        })

    return render(request, "reports/report_email.html", {
        # TODO: move the responsibility for safety up the chain, to scheduled reports, etc
        'email_content': mark_safe(content),  # nosec: content is expected to be the report's HTML
        'unsub_link': unsub_link
    })


@login_and_domain_required
@conditionally_location_safe(location_restricted_scheduled_reports_enabled)
def view_scheduled_report(request, domain, scheduled_report_id):
    report_text = get_scheduled_report_response(request.couch_user, domain, scheduled_report_id, email=False)[0]
    return render_full_report_notification(request, report_text)


def _get_form_context(request, domain, instance):
    timezone = get_timezone_for_user(request.couch_user, domain)
    try:
        assert domain == instance.domain
    except AssertionError:
        raise Http404()

    context = {
        "domain": domain,
        "timezone": timezone,
        "instance": instance,
        "user": request.couch_user,
        "request": request,
    }
    return context


def _get_form_render_context(request, domain, instance, case_id=None):
    context = _get_form_context(request, domain, instance)
    user = context['user']
    timezone = context['timezone']
    support_enabled = toggle_enabled(request, toggles.SUPPORT)

    form_data, question_list_not_found = get_readable_data_for_submission(instance)

    # Build ordered list of questions and dict of question values => responses
    # Question values will be formatted to be processed by XFormQuestionValueIterator,
    # for example "/data/group/repeat_group[2]/question_id"
    try:
        question_response_map, ordered_question_values = get_data_cleaning_data(form_data, instance)
    except AttributeError as err:
        question_response_map, ordered_question_values = (None, None)
        import logging
        logging.exception(err)

    context.update({
        "context_case_id": case_id,
        "instance": instance,
        "is_archived": instance.is_archived,
        "form_source_download_url": get_form_source_download_url(instance),
        "edit_info": _get_edit_info(instance),
        "domain": domain,
        "question_list_not_found": question_list_not_found,
        "form_data": form_data,
        "question_response_map": question_response_map,
        "ordered_question_values": ordered_question_values,
        "tz_abbrev": timezone.localize(datetime.utcnow()).tzname(),
    })

    context.update(_get_cases_changed_context(domain, instance, case_id))
    context.update(_get_form_metadata_context(domain, instance, timezone, support_enabled))
    context.update(_get_display_options(request, domain, user, instance, support_enabled))
    context.update(_get_edit_info(instance))

    instance_history = []
    if instance.history:
        form_operations = {
            'archive': gettext_lazy('Archive'),
            'unarchive': gettext_lazy('Un-Archive'),
            'edit': gettext_lazy('Edit'),
            'uuid_data_fix': gettext_lazy('Duplicate ID fix')
        }
        for operation in instance.history:
            user_date = ServerTime(operation.date).user_time(timezone).done()
            instance_history.append({
                'readable_date': user_date.strftime(DATE_FORMAT),
                'readable_action': form_operations.get(operation.operation, operation.operation),
                'user_info': get_doc_info_by_id(domain, operation.user),
            })
    context['instance_history'] = instance_history

    return context


def _get_cases_changed_context(domain, form, case_id=None):
    case_blocks = extract_case_blocks(form)
    for i, block in enumerate(list(case_blocks)):
        if case_id and block.get(const.CASE_ATTR_ID) == case_id:
            case_blocks.pop(i)
            case_blocks.insert(0, block)
    cases = []

    for case_block in case_blocks:
        this_case_id = case_block.get(const.CASE_ATTR_ID)
        try:
            this_case = CommCareCase.objects.get_case(this_case_id, domain) if this_case_id else None
            valid_case = True
        except ResourceNotFound:
            this_case = None
            valid_case = False

        if this_case and this_case.case_id:
            url = reverse('case_data', args=[domain, this_case.case_id])
        else:
            url = "#"

        assume_phonetimes = not form.metadata or form.metadata.deviceID != CLOUDCARE_DEVICE_ID
        cases.append({
            "is_current_case": case_id and this_case_id == case_id,
            "name": case_inline_display(this_case),
            "properties": _get_properties_display(case_block, assume_phonetimes, get_timezone_for_request()),
            "url": url,
            "valid_case": valid_case,
            "case_type": this_case.type if this_case and valid_case else None,
        })

    return {
        'cases': cases
    }


def _get_properties_display(case_block, assume_phonetimes, timezone):
    definitions = [
        DisplayConfig(expr=k, is_phone_time=assume_phonetimes)
        # Sort with common @ attributes at the bottom
        for k in sorted(case_block.keys(), key=lambda k: (k[0] == '@', k))
    ]
    return [get_display_data(case_block, definition, timezone=timezone) for definition in definitions]


def _get_form_metadata_context(domain, form, timezone, support_enabled=False):
    meta = form.metadata.to_json() if form.metadata else {}
    meta['@xmlns'] = form.xmlns
    meta['received_on'] = json_format_datetime(form.received_on)
    meta['server_modified_on'] = json_format_datetime(form.server_modified_on) if form.server_modified_on else ''
    if support_enabled:
        meta['last_sync_token'] = form.last_sync_token

    if getattr(form, 'auth_context', None):
        auth_context = AuthContext(form.auth_context)
        auth_context_user_id = auth_context.user_id
        auth_user_info = get_doc_info_by_id(None, auth_context_user_id)
    else:
        auth_user_info = get_doc_info_by_id(domain, None)
        auth_context = AuthContext(
            user_id=None,
            authenticated=False,
            domain=domain,
        )
    meta_userID = meta.get('userID')
    meta_username = meta.get('username')
    if meta_userID == 'demo_user':
        user_info = DocInfo(
            domain=domain,
            display='demo_user',
        )
    elif meta_username in ('admin', 'system'):
        user_info = DocInfo(
            domain=domain,
            display=meta_username,
        )
    else:
        user_info = get_doc_info_by_id(None, meta_userID)

    return {
        "form_meta_data": _get_meta_data_display(meta, timezone),
        "auth_context": auth_context,
        "auth_user_info": auth_user_info,
        "user_info": user_info,
    }


def _get_meta_data_display(meta, timezone):
    phonetime_fields = {'timeStart', 'timeEnd'}
    date_fields = {'received_on', 'server_modified_on'} | phonetime_fields
    definitions = [DisplayConfig(
        expr=k,
        is_phone_time=k in phonetime_fields,
        process="date" if k in date_fields else None,
    ) for k in _sorted_form_metadata_keys(list(meta))]
    return [get_display_data(meta, definition, timezone=timezone) for definition in definitions]


def _sorted_form_metadata_keys(keys):
    def mycmp(x, y):
        foo = ('timeStart', 'timeEnd')
        bar = ('username', 'userID')

        if x in foo and y in foo:
            return -1 if foo.index(x) == 0 else 1
        elif x in foo or y in foo:
            return 0

        if x in bar and y in bar:
            return -1 if bar.index(x) == 0 else 1
        elif x in bar and y in bar:
            return 0

        return cmp(x, y)
    return sorted(keys, key=cmp_to_key(mycmp))


def _get_edit_info(instance):
    info = {
        'was_edited': False,
        'is_edit': False,
    }
    if instance.is_deprecated:
        info.update({
            'was_edited': True,
            'latest_version': instance.orig_id,
        })
    if getattr(instance, 'edited_on', None) and getattr(instance, 'deprecated_form_id', None):
        info.update({
            'is_edit': True,
            'edited_on': instance.edited_on,
            'previous_version': instance.deprecated_form_id
        })
    return info


def _get_display_options(request, domain, user, form, support_enabled):
    user_can_edit = (
        request and user and request.domain and user.can_edit_data()
    )
    show_edit_options = (
        user_can_edit
        and can_edit_form_location(domain, user, form)
    )
    show_edit_submission = (
        user_can_edit
        and has_privilege(request, privileges.DATA_CLEANUP)
        and not form.is_deprecated
    )

    show_resave = (
        user_can_edit and support_enabled
    )

    return {
        "show_edit_options": show_edit_options,
        "show_edit_submission": show_edit_submission,
        "show_resave": show_resave,
    }


def safely_get_form(request, domain, instance_id):
    """Fetches a form and verifies that the user can access it."""
    form = get_form_or_404(domain, instance_id)
    if not can_edit_form_location(domain, request.couch_user, form):
        raise location_restricted_exception(request)
    return form


@location_safe
class FormDataView(BaseProjectReportSectionView):
    urlname = 'render_form_data'
    page_title = gettext_lazy("Untitled Form")
    template_name = "reports/reportdata/bootstrap3/form_data.html"
    http_method_names = ['get']

    @method_decorator(require_form_view_permission)
    def dispatch(self, request, *args, **kwargs):
        return super(FormDataView, self).dispatch(request, *args, **kwargs)

    @property
    def instance_id(self):
        return self.kwargs['instance_id']

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain, self.instance_id,))

    @property
    @memoized
    def xform_instance(self):
        return safely_get_form(self.request, self.domain, self.instance_id)

    @property
    @memoized
    def form_name(self):
        try:
            form_name = self.xform_instance.form_data["@name"]
        except KeyError:
            form_name = _("Untitled Form")
        return form_name

    @property
    def page_name(self):
        return self.form_name

    @property
    def parent_pages(self):
        return [{
            'title': inspect.SubmitHistory.name,
            'url': inspect.SubmitHistory.get_url(self.domain),
        }]

    @property
    def page_context(self):
        page_context = _get_form_render_context(self.request, self.domain, self.xform_instance)
        page_context.update({
            "slug": inspect.SubmitHistory.slug,
            "form_name": self.form_name,
            "form_received_on": self.xform_instance.received_on,
        })
        return page_context


@login_and_domain_required
@require_form_view_permission
@location_safe
def view_form_attachment(request, domain, instance_id, attachment_id):
    # This view differs from corehq.apps.api.object_fetch_api.view_form_attachment
    # by using login_and_domain_required as auth to allow domain aware login page
    # in browser
    # This is not used in HQ anywhere but the link for the same is created
    # in the apps and saved as case properties
    # example: https://india.commcarehq.org/a/gcc-sangath/reports/case_data/b7dcdb76-d58a-4aa6-80d1-de35d7f600d0/
    # View image/audio/video form attachment in browser
    # download option is restricted in html for audio/video if FF enabled
    _ensure_form_access(request, domain, instance_id, attachment_id)
    attachment_meta = XFormInstance.objects.get_attachment_by_name(instance_id, attachment_id)
    context = {
        'download_url': reverse('api_form_attachment', args=[domain, instance_id, attachment_id]),
        'content_name': attachment_id,
        'disable_download': toggles.DISABLE_FORM_ATTACHMENT_DOWNLOAD_IN_BROWSER.enabled_for_request(request),
        'is_image': attachment_meta.is_image
    }
    return render(
        request,
        template_name='reports/reportdata/view_form_attachment.html',
        context=context
    )


def _ensure_form_access(request, domain, instance_id, attachment_id):
    if not instance_id or not attachment_id:
        raise Http404

    # this raises a PermissionDenied error if necessary
    safely_get_form(request, domain, instance_id)


def get_form_attachment_response(request, domain, instance_id=None, attachment_id=None):
    _ensure_form_access(request, domain, instance_id, attachment_id)

    try:
        content = XFormInstance.objects.get_attachment_content(instance_id, attachment_id)
    except AttachmentNotFound:
        raise Http404

    return get_download_response(
        payload=content.content_stream,
        content_length=content.content_length,
        content_type=content.content_type,
        download=False,
        filename=attachment_id,
        request=request
    )


@location_safe
@require_form_view_permission
@login_and_domain_required
@require_GET
def case_form_data(request, domain, case_id, xform_id):
    instance = get_form_or_404(domain, xform_id)
    if not can_edit_form_location(domain, request.couch_user, instance):
        # This can happen if a user can view the case but not a particular form
        return JsonResponse({
            'html': _("You do not have permission to view this form."),
        }, status=403)
    context = _get_form_render_context(request, domain, instance, case_id)
    return JsonResponse({
        'html': render_to_string("reports/form/partials/bootstrap3/single_form.html", context, request=request),
        'xform_id': xform_id,
        'question_response_map': context['question_response_map'],
        'ordered_question_values': context['ordered_question_values'],
    })


@require_form_view_permission
@login_and_domain_required
@require_GET
def download_form(request, domain, instance_id):
    instance = get_form_or_404(domain, instance_id)
    assert (domain == instance.domain)

    response = HttpResponse(content_type='application/xml')
    response.write(instance.get_xml())
    return response


@require_form_view_permission
@require_permission(HqPermissions.edit_data)
@require_POST
@location_safe
def restore_edit(request, domain, instance_id):
    if not (has_privilege(request, privileges.DATA_CLEANUP)):
        raise Http404()

    instance = safely_get_form(request, domain, instance_id)
    if instance.is_deprecated:
        submit_form_locally(instance.get_xml(), domain, app_id=instance.app_id, build_id=instance.build_id)
        messages.success(request, _('Form was restored from a previous version.'))
        return HttpResponseRedirect(reverse('render_form_data', args=[domain, instance.orig_id]))
    else:
        messages.warning(request, _('Sorry, that form cannot be edited.'))
        return HttpResponseRedirect(reverse('render_form_data', args=[domain, instance_id]))


@require_form_view_permission
@require_permission(HqPermissions.edit_data)
@require_POST
@location_safe
def archive_form(request, domain, instance_id):
    instance = safely_get_form(request, domain, instance_id)
    assert instance.domain == domain
    case_id_from_request, redirect = _get_case_id_and_redirect_url(domain, request)

    notify_level = messages.SUCCESS
    if instance.is_normal:
        cases_with_other_forms = _get_cases_with_other_forms(domain, instance)
        if cases_with_other_forms:
            notify_msg = _get_cases_with_forms_message(domain, cases_with_other_forms, case_id_from_request)
            notify_level = messages.ERROR
        else:
            instance.archive(user_id=request.couch_user._id)
            revert_api_request_from_form(instance_id)
            notify_msg = _("Form was successfully archived.")
    elif instance.is_archived:
        notify_msg = _("Form was already archived.")
    else:
        notify_msg = _("Can't archive documents of type %s. How did you get here??") % instance.doc_type
        notify_level = messages.ERROR

    params = {
        "notif": notify_msg,
        "undo": _("Undo"),
        "url": reverse('unarchive_form', args=[domain, instance_id]),
    }

    msg_template = "{notif} <a href='{url}' class='post-link'>{undo}</a>" if instance.is_archived else '{notif}'
    msg = format_html(msg_template, **params)
    messages.add_message(request, notify_level, msg, extra_tags='html')

    return HttpResponseRedirect(redirect)


@require_form_view_permission
@require_permission(HqPermissions.edit_data)
@require_POST
@location_safe
def soft_delete_form(request, domain, instance_id):
    form = safely_get_form(request, domain, instance_id)
    assert form.domain == domain
    if form.is_archived:
        form.soft_delete()
        return HttpResponseRedirect(reverse('project_report_dispatcher',
                                            args=(domain, 'submit_history')))
    else:
        return HttpResponseForbidden(
            _(f"Cannot delete form {instance_id} because it is not archived.")
        )


def _get_cases_with_forms_message(domain, cases_with_other_forms, case_id_from_request):
    def _get_all_case_links():
        all_case_links = []
        for case_id, case_name in cases_with_other_forms.items():
            if case_id == case_id_from_request:
                all_case_links.append(format_html(
                    _("{} (this case)"),
                    case_name
                ))
            else:
                all_case_links.append(format_html(
                    '<a href="{}#!history">{}</a>',
                    reverse("case_data", args=[domain, case_id]),
                    case_name
                ))
        return all_case_links

    case_links = format_html_join(", ", "{}", ((link,) for link in _get_all_case_links()))

    msg = _("""Form cannot be archived as it creates cases that are updated by other forms.
        All other forms for these cases must be archived first:""")
    return format_html("{} {}", msg, case_links)


def _get_cases_with_other_forms(domain, xform):
    """Get all cases touched by this form which also have other forms associated with them.
    :returns: Dict of Case ID -> Case"""
    cases_created = {u.id for u in get_case_updates(xform) if u.creates_case()}
    cases = {}
    for case in CommCareCase.objects.iter_cases(cases_created, domain):
        if not case.is_deleted and case.xform_ids != [xform.form_id]:
            # case has other forms that need to be archived before this one
            cases[case.case_id] = case.name
    return cases


def _get_case_id_and_redirect_url(domain, request):
    case_id = None
    redirect = request.META.get('HTTP_REFERER')
    if not redirect:
        redirect = inspect.SubmitHistory.get_url(domain)
    else:
        # check if referring URL was a case detail view, then make sure
        # the case still exists before redirecting.
        template = reverse('case_data', args=[domain, 'fake_case_id'])
        template = template.replace('fake_case_id', '([^/]*)')
        case_id = re.findall(template, redirect)
        if case_id:
            case_id = case_id[0]
            try:
                case = CommCareCase.objects.get_case(case_id, domain)
                if case.is_deleted:
                    raise CaseNotFound
            except CaseNotFound:
                redirect = reverse('project_report_dispatcher', args=[domain, 'case_list'])
    return case_id, redirect


@require_form_view_permission
@require_permission(HqPermissions.edit_data)
@location_safe
def unarchive_form(request, domain, instance_id):
    instance = safely_get_form(request, domain, instance_id)
    assert instance.domain == domain
    if instance.is_archived:
        instance.unarchive(user_id=request.couch_user._id)
    else:
        assert instance.is_normal
    messages.success(request, _("Form was successfully restored."))

    redirect = request.META.get('HTTP_REFERER')
    if not redirect:
        redirect = reverse('render_form_data', args=[domain, instance_id])
    return HttpResponseRedirect(redirect)


def get_data_cleaning_updates(request, old_properties):
    updates = {}
    properties = json.loads(request.POST.get('properties'))

    def _get_value(val_or_dict):
        if isinstance(val_or_dict, dict):
            return val_or_dict.get('value')
        else:
            return val_or_dict

    for prop, value in properties.items():
        if prop not in old_properties or _get_value(old_properties[prop]) != value:
            updates[prop] = value
    return updates


@require_form_view_permission
@require_permission(HqPermissions.edit_data)
@require_POST
@location_safe
def edit_form(request, domain, instance_id):
    instance = safely_get_form(request, domain, instance_id)
    assert instance.domain == domain

    form_data, question_list_not_found = get_readable_data_for_submission(instance)
    old_properties, dummy = get_data_cleaning_data(form_data, instance)
    updates = get_data_cleaning_updates(request, old_properties)

    if updates:
        errors = FormProcessorInterface(domain).update_responses(instance, updates, request.couch_user.get_id)
        if errors:
            messages.error(request, _('Could not update questions: {}').format(", ".join(errors)))
        else:
            messages.success(request, _('Question responses saved.'))
    else:
        messages.info(request, _('No changes made to form.'))

    return JsonResponse({'success': 1})


@require_form_view_permission
@require_permission(HqPermissions.edit_data)
@require_POST
@location_safe
def resave_form_view(request, domain, instance_id):
    """Re-save the form to have it re-processed by pillows
    """
    instance = safely_get_form(request, domain, instance_id)
    assert instance.domain == domain
    resave_form(domain, instance)
    messages.success(request, _("Form was successfully resaved. It should reappear in reports shortly."))
    return HttpResponseRedirect(reverse('render_form_data', args=[domain, instance_id]))


def _is_location_safe_report_class(view_fn, request, domain, export_hash, format):
    db = get_blob_db()

    try:
        meta = db.metadb.get(parent_id=export_hash, key=export_hash)
    except models.BlobMeta.DoesNotExist:
        # The report doesn't exist, so let the export code handle the response
        return True

    return report_class_is_location_safe(meta.properties["report_class"])


# TODO: This should be renamed to better convey what the function does.
# Export suggests that this is exporting data, but this is actually the function
# that retrieves the data that was previously exported.
@conditionally_location_safe(_is_location_safe_report_class)
@login_and_domain_required
@require_GET
def export_report(request, domain, export_hash, format):
    db = get_blob_db()
    report_not_found = HttpResponseNotFound(_("That report was not found. Please remember "
                                              "that download links expire after 24 hours."))

    try:
        meta = db.metadb.get(parent_id=export_hash, key=export_hash)
    except models.BlobMeta.DoesNotExist:
        return report_not_found

    if domain != meta.domain:
        raise Http404()

    report_class = meta.properties["report_class"]

    try:
        report_file = db.get(export_hash, type_code=CODES.tempfile)
    except NotFound:
        return report_not_found
    with report_file:
        if not request.couch_user.has_permission(domain, 'view_report', data=report_class):
            raise PermissionDenied()
        if format in Format.VALID_FORMATS:
            file = ContentFile(report_file.read())
            response = HttpResponse(file, Format.FORMAT_DICT[format])
            response['Content-Length'] = file.size
            response['Content-Disposition'] = 'attachment; filename="{filename}.{extension}"'.format(
                filename=meta.name or export_hash,
                extension=Format.FORMAT_DICT[format]['extension']
            )
            return response
        else:
            return HttpResponseNotFound(_("We don't support this format"))


@require_permission(HqPermissions.view_report,
                    'corehq.apps.reports.standard.project_health.ProjectHealthDashboard')
def project_health_user_details(request, domain, user_id):
    # todo: move to project_health.py? goes with project health dashboard.
    user = get_document_or_404(CommCareUser, domain, user_id)
    submission_by_form_link = '{}?emw=u__{}'.format(
        reverse('project_report_dispatcher', args=(domain, 'submissions_by_form')),
        user_id,
    )
    return render(request, 'reports/project_health/user_details.html', {
        'domain': domain,
        'user': user,
        'groups': ', '.join(g.name for g in Group.by_user_id(user_id)),
        'submission_by_form_link': submission_by_form_link,
    })


class TableauServerView(BaseProjectReportSectionView):
    urlname = 'tableau_server_view'
    page_title = gettext_lazy('Tableau Server Config')
    template_name = 'hqwebapp/crispy/single_crispy_form.html'

    @method_decorator(require_superuser)
    @method_decorator(toggles.EMBEDDED_TABLEAU.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(TableauServerView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def tableau_server_form(self):
        data = self.request.POST if self.request.method == 'POST' else None
        return TableauServerForm(
            data, domain=self.domain, user_syncing_config=self.get_user_syncing_config()
        )

    def get_user_syncing_config(self):
        '''
        returns a dict --
            {
                'user_syncing_enabled': Bool; is FF enabled
                'all_tableau_groups': List or None; all tableau groups on linked Tableau site
                'server_reachable': Bool or None; could Tableau Server be reached
            }
        '''
        user_syncing_config = {}
        user_syncing_config['user_syncing_enabled'] = TABLEAU_USER_SYNCING.enabled(self.domain)
        if user_syncing_config['user_syncing_enabled']:
            if TableauConnectedApp.get_server(self.domain):
                try:
                    user_syncing_config['all_tableau_groups'] = get_all_tableau_groups(self.domain)
                    user_syncing_config['server_reachable'] = True
                except TableauAPIError:
                    messages.warning(self.request, _("""Cannot reach Tableau Server right now, allowed Tableau
                                                        groups cannot be edited."""))
            else:
                messages.warning(self.request, _("""Tableau Server is not configured yet, allowed Tableau groups
                                                    cannot be edited."""))
        return user_syncing_config

    @property
    def page_context(self):
        return {
            'form': self.tableau_server_form
        }

    def post(self, request, *args, **kwargs):
        if self.tableau_server_form.is_valid():
            self.tableau_server_form.save()
            messages.success(
                request, gettext_lazy("Tableau Server Settings Updated")
            )
        else:
            messages.error(
                request, gettext_lazy("Could not update Tableau Server Settings")
            )
        return self.get(request, *args, **kwargs)


class TableauVisualizationListView(BaseProjectReportSectionView, CRUDPaginatedViewMixin):
    urlname = 'tableau_visualization_list_view'
    page_title = _('Tableau Visualizations')
    template_name = 'reports/tableau_visualization.html'

    @method_decorator(toggles.EMBEDDED_TABLEAU.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(TableauVisualizationListView, self).dispatch(request, *args, **kwargs)

    @property
    def total(self):
        return self.base_query.count()

    @property
    def base_query(self):
        return TableauVisualization.objects.filter(domain=self.domain)

    @property
    def column_names(self):
        return [
            _("Title"),
            _("Server"),
            _("View URL"),
        ]

    @property
    def page_context(self):
        return self.pagination_context

    @property
    def paginated_list(self):
        start, end = self.skip, self.skip + self.limit
        for tableau_visualization in self.base_query.all()[start:end]:
            yield {
                "itemData": self._get_item_data(tableau_visualization),
                "template": "tableau-visualization-template",
            }

    def _get_item_data(self, tableau_visualization):
        data = {
            'id': tableau_visualization.id,
            'title': tableau_visualization.title,
            'server': tableau_visualization.server.server_name,
            'view_url': tableau_visualization.view_url,
            'updateForm': self.get_update_form_response(
                self.get_update_form(tableau_visualization)
            ),
        }
        return data

    def get_deleted_item_data(self, item_id):
        tableau_viz = TableauVisualization.objects.get(
            pk=item_id,
            domain=self.domain,
        )
        tableau_viz.delete()
        return {
            'itemData': self._get_item_data(tableau_viz),
            'template': 'tableau-visualization-deleted-template',
        }

    def get_update_form(self, instance=None):
        if instance is None:
            instance = TableauVisualization.objects.get(
                pk=self.request.POST.get("id"),
                domain=self.domain,
            )
        if self.request.method == 'POST' and self.action == 'update':
            return UpdateTableauVisualizationForm(self.domain, self.request.POST, instance=instance)
        return UpdateTableauVisualizationForm(self.domain, instance=instance)

    def get_updated_item_data(self, update_form):
        tableau_viz = update_form.save()
        return {
            "itemData": self._get_item_data(tableau_viz),
            "template": "tableau-visualization-template",
        }

    def post(self, *args, **kwargs):
        return self.paginate_crud_response


class TableauVisualizationDetailView(BaseProjectReportSectionView, ModelFormMixin, ProcessFormView):
    urlname = 'tableau_visualization_detail_view'
    page_title = _('Tableau Visualization')
    template_name = 'hqwebapp/crispy/single_crispy_form.html'
    model = TableauVisualization
    form_class = TableauVisualizationForm

    @method_decorator(toggles.EMBEDDED_TABLEAU.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(TableauVisualizationDetailView, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().filter(domain=self.domain)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object() if self.pk_url_kwarg in self.kwargs else None
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object() if self.pk_url_kwarg in self.kwargs else None
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['domain'] = self.domain
        return kwargs

    def get_success_url(self):
        return reverse(
            TableauVisualizationListView.urlname,
            kwargs={'domain': self.domain},
        )

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


@login_and_domain_required
@location_safe
@require_POST
def get_or_create_filter_hash(request, domain):
    query_id = request.POST.get('query_id')
    query_string = request.POST.get('params')
    not_found = False
    max_input_limit = 4500

    if query_string:
        if len(query_string) > max_input_limit:
            not_found = True
        else:
            query, created = QueryStringHash.objects.get_or_create(query_string=query_string, domain=domain)
            query_id = query.query_id.hex
            query.save()  # Updates the 'last_accessed' field
    elif query_id:
        try:
            query = QueryStringHash.objects.filter(query_id=query_id, domain=domain)
        except ValidationError:
            query = None
        if not query:
            not_found = True
        else:
            query = query[0]
            query_string = query.query_string
            query.save()  # Updates the 'last_accessed' field
    else:
        not_found = True

    return JsonResponse({
        'query_string': query_string,
        'query_id': query_id,
        'not_found': not_found,
    })


@require_POST
@toggles.COPY_CASES.required_decorator()
@require_permission(HqPermissions.edit_data)
@requires_privilege(privileges.CASE_COPY)
@location_safe
def copy_cases(request, domain, *args, **kwargs):
    from corehq.apps.hqcase.case_helper import CaseCopier
    body = json.loads(request.body)

    case_ids = body.get('case_ids')
    if not case_ids:
        return JsonResponse({'error': _("Missing case ids")}, status=400)

    new_owner = body.get('owner_id')
    if not new_owner:
        return JsonResponse({'error': _("Missing new owner id")}, status=400)

    censor_data = {
        prop['name']: prop['label']
        for prop in body.get('sensitive_properties', [])
    }

    case_copier = CaseCopier(
        domain,
        to_owner=new_owner,
        censor_data=censor_data,
    )
    case_id_pairs, errors = case_copier.copy_cases(case_ids)
    count = len(case_id_pairs)
    return JsonResponse(
        {'copied_cases': count, 'error': errors},
        status=400 if count == 0 else 200,
    )
