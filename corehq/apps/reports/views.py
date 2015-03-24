from StringIO import StringIO
from copy import copy
import os
import json
import tempfile
import re
import zipfile
import cStringIO
import itertools
from datetime import datetime, timedelta, date
from urllib2 import URLError
from corehq.util.timezones.utils import get_timezone_for_user
from dimagi.utils.decorators.memoized import memoized
from unidecode import unidecode
from dateutil.parser import parse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.cache import cache
from django.core.servers.basehttp import FileWrapper
from django.core.urlresolvers import reverse
from django.http import (HttpResponseRedirect,
    HttpResponseBadRequest, Http404, HttpResponseForbidden)
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.views.decorators.http import (require_http_methods,
    require_POST)
from couchdbkit.exceptions import ResourceNotFound
from django.core.files.base import ContentFile
from django.http.response import HttpResponse, HttpResponseNotFound
from django.views.decorators.http import require_GET
from django.views.generic import View
import pytz
from casexml.apps.stock.models import StockTransaction
from corehq import toggles, Domain
from casexml.apps.case.cleanup import rebuild_case, close_case
from corehq.apps.products.models import SQLProduct
from corehq.apps.data_interfaces.dispatcher import DataInterfaceDispatcher
from corehq.apps.reports.display import FormType
from corehq.apps.reports.forms import SavedReportConfigForm
from corehq.util.couch import get_document_or_404
from corehq.util.view_utils import absolute_reverse

import couchexport
from couchexport import views as couchexport_views
from couchexport.exceptions import (
    CouchExportException,
    SchemaMismatchException
)
from couchexport.groupexports import rebuild_export
from couchexport.models import FakeSavedExportSchema, SavedBasicExport
from couchexport.shortcuts import (export_data_shared, export_raw_data,
    export_response)
from couchexport.tasks import rebuild_schemas
from couchexport.util import SerializableFunction
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.bulk import wrapped_docs
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.couch.loosechange import parse_date
from dimagi.utils.decorators.datespan import datespan_in_request
from dimagi.utils.export import WorkBook
from dimagi.utils.logging import notify_exception
from dimagi.utils.parsing import json_format_datetime, string_to_boolean, string_to_datetime, json_format_date
from dimagi.utils.web import json_request, json_response
from soil import DownloadBase
from soil.tasks import prepare_download
from dimagi.utils.couch.cache.cache_core import get_redis_client
from couchexport.export import Format, export_from_tables
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.templatetags.case_tags import case_inline_display
from casexml.apps.case.xml import V2
from corehq.apps.export.exceptions import BadExportConfiguration
from corehq.apps.hqwebapp.models import ReportsTab
from corehq.apps.reports.exportfilters import default_form_filter
import couchforms.views as couchforms_views
from couchforms.filters import instances
from couchforms.models import XFormInstance, doc_types
from corehq.apps.reports.templatetags.xform_tags import render_form
from filters.users import UserTypeFilter
from corehq.apps.domain.decorators import (login_or_digest)
from corehq.apps.export.custom_export_helpers import CustomExportHelper
from corehq.apps.groups.models import Group
from corehq.apps.hqcase.export import export_cases
from corehq.apps.reports.dispatcher import ProjectReportDispatcher
from corehq.apps.reports.models import (
    ReportConfig,
    ReportNotification,
    FakeFormExportSchema,
    FormExportSchema,
    HQGroupExportConfiguration
)
from corehq.apps.reports.standard.cases.basic import CaseListReport
from corehq.apps.reports.tasks import create_metadata_export, rebuild_export_async
from corehq.apps.reports import util
from corehq.apps.reports.util import (
    get_all_users_by_domain,
    users_matching_filter,
)
from corehq.apps.reports.standard import inspect, export, ProjectReport
from corehq.apps.reports.export import (ApplicationBulkExportHelper,
    CustomBulkExportHelper, save_metadata_export_to_tempfile)
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.export import export_users
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.models import Permissions
from corehq.apps.domain.decorators import login_and_domain_required

from casexml.apps.case.xform import extract_case_blocks

DATE_FORMAT = "%Y-%m-%d"

datespan_default = datespan_in_request(
    from_param="startdate",
    to_param="enddate",
    default_days=7,
)

require_form_export_permission = require_permission(Permissions.view_report, 'corehq.apps.reports.standard.export.ExcelExportReport', login_decorator=None)
require_case_export_permission = require_permission(Permissions.view_report, 'corehq.apps.reports.standard.export.CaseExportReport', login_decorator=None)

require_form_view_permission = require_permission(Permissions.view_report, 'corehq.apps.reports.standard.inspect.SubmitHistory', login_decorator=None)
require_case_view_permission = require_permission(Permissions.view_report, 'corehq.apps.reports.standard.cases.basic.CaseListReport', login_decorator=None)

require_can_view_all_reports = require_permission(Permissions.view_reports)


def can_view_attachments(request):
    return (
        request.couch_user.has_permission(
            request.domain, 'view_report',
            data='corehq.apps.reports.standard.cases.basic.CaseListReport'
        )
        or toggles.ALLOW_CASE_ATTACHMENTS_VIEW.enabled(request.user.username)
        or toggles.ALLOW_CASE_ATTACHMENTS_VIEW.enabled(request.domain)
    )


@login_and_domain_required
def default(request, domain):
    module = Domain.get_module_by_name(domain)
    if hasattr(module, 'DEFAULT_REPORT_CLASS'):
        return HttpResponseRedirect(getattr(module, 'DEFAULT_REPORT_CLASS').get_url(domain))
    return HttpResponseRedirect(reverse(saved_reports, args=[domain]))

@login_and_domain_required
def old_saved_reports(request, domain):
    return default(request, domain)


@login_and_domain_required
def saved_reports(request, domain, template="reports/reports_home.html"):
    user = request.couch_user
    if not (request.couch_user.can_view_reports()
            or request.couch_user.get_viewable_reports()):
        raise Http404

    configs = ReportConfig.by_domain_and_owner(domain, user._id)

    def _is_valid(rn):
        # the _id check is for weird bugs we've seen in the wild that look like
        # oddities in couch.
        return hasattr(rn, "_id") and rn._id and (not hasattr(rn, 'report_slug') or rn.report_slug != 'admin_domains')

    scheduled_reports = [rn for rn in ReportNotification.by_domain_and_owner(domain, user._id) if _is_valid(rn)]
    scheduled_reports = sorted(scheduled_reports, key=lambda rn: rn.configs[0].name)
    for report in scheduled_reports:
        time_difference = get_timezone_difference(domain)
        (report.hour, day_change) = recalculate_hour(report.hour, int(time_difference[:3]), int(time_difference[3:]))
        report.minute = 0
        if day_change:
            report.day = calculate_day(report.interval, report.day, day_change)

    context = dict(
        couch_user=request.couch_user,
        domain=domain,
        configs=configs,
        scheduled_reports=scheduled_reports,
        report=dict(
            title=_("My Saved Reports"),
            show=user.can_view_reports() or user.get_viewable_reports(),
            slug=None,
            is_async=True,
            section_name=ProjectReport.section_name,
        ),
    )

    if request.couch_user:
        util.set_report_announcements_for_user(request, user)

    return render(request, template, context)

@login_or_digest
@require_form_export_permission
@datespan_default
@require_GET
def export_data(req, domain):
    """
    Download all data for a couchdbkit model
    """
    try:
        export_tag = json.loads(req.GET.get("export_tag", "null") or "null")
    except ValueError:
        return HttpResponseBadRequest()

    include_errors = string_to_boolean(req.GET.get("include_errors", False))

    kwargs = {"format": req.GET.get("format", Format.XLS_2007),
              "previous_export_id": req.GET.get("previous_export", None),
              "filename": export_tag,
              "use_cache": string_to_boolean(req.GET.get("use_cache", "True")),
              "max_column_size": int(req.GET.get("max_column_size", 2000)),
              "separator": req.GET.get("separator", "|")}

    user_filter, _ = UserTypeFilter.get_user_filter(req)

    if user_filter:
        filtered_users = users_matching_filter(domain, user_filter)

        def _ufilter(user):
            try:
                return user['form']['meta']['userID'] in filtered_users
            except KeyError:
                return False
        filter = _ufilter
    else:
        group = util.get_group(**json_request(req.GET))
        filter = SerializableFunction(util.group_filter, group=group)

    errors_filter = instances if not include_errors else None

    kwargs['filter'] = couchexport.util.intersect_functions(filter, errors_filter)
    if kwargs['format'] == 'raw':
        resp = export_raw_data([domain, export_tag], filename=export_tag)
    else:
        try:
            resp = export_data_shared([domain, export_tag], **kwargs)
        except CouchExportException as e:
            return HttpResponseBadRequest(e)
    if resp:
        return resp
    else:
        messages.error(req, "Sorry, there was no data found for the tag '%s'." % export_tag)
        next = req.GET.get("next", "")
        if not next:
            next = export.ExcelExportReport.get_url(domain=domain)
        return HttpResponseRedirect(next)

@require_form_export_permission
@login_and_domain_required
@datespan_default
@require_GET
def export_data_async(request, domain):
    """
    Download all data for a couchdbkit model
    """
    try:
        export_tag = json.loads(request.GET.get("export_tag", "null") or "null")
        export_type = request.GET.get("type", "form")
    except ValueError:
        return HttpResponseBadRequest()
    assert(export_tag[0] == domain)

    filter = util.create_export_filter(request, domain, export_type=export_type)

    return couchexport_views.export_data_async(request, filter=filter, type=export_type)


@login_or_digest
@datespan_default
def export_default_or_custom_data(request, domain, export_id=None, bulk_export=False):
    """
    Export data from a saved export schema
    """
    r = request.POST if request.method == 'POST' else request.GET
    deid = r.get('deid') == 'true'
    if deid:
        return _export_deid(request, domain, export_id, bulk_export=bulk_export)
    else:
        return _export_no_deid(request, domain, export_id, bulk_export=bulk_export)

@require_permission('view_report', 'corehq.apps.reports.standard.export.DeidExportReport', login_decorator=None)
def _export_deid(request, domain, export_id=None, bulk_export=False):
    return _export_default_or_custom_data(request, domain, export_id, bulk_export=bulk_export, safe_only=True)

@require_form_export_permission
def _export_no_deid(request, domain, export_id=None, bulk_export=False):
    return _export_default_or_custom_data(request, domain, export_id, bulk_export=bulk_export)

def _export_default_or_custom_data(request, domain, export_id=None, bulk_export=False, safe_only=False):
    req = request.POST if request.method == 'POST' else request.GET
    async = req.get('async') == 'true'
    next = req.get("next", "")
    format = req.get("format", "")
    export_type = req.get("type", "form")
    previous_export_id = req.get("previous_export", None)
    filename = req.get("filename", None)
    max_column_size = int(req.get("max_column_size", 2000))
    limit = int(req.get("limit", 0))

    filter = util.create_export_filter(request, domain, export_type=export_type)
    if bulk_export:
        try:
            is_custom = json.loads(req.get("is_custom", "false"))
            export_tags = json.loads(req.get("export_tags", "null") or "null")
        except ValueError:
            return HttpResponseBadRequest()

        export_helper = (CustomBulkExportHelper if is_custom else ApplicationBulkExportHelper)(
            domain=domain,
            safe_only=safe_only
        )

        if export_type == 'form':
            filter &= SerializableFunction(instances)

        return export_helper.prepare_export(export_tags, filter)

    elif export_id:
        # this is a custom export
        try:
            export_object = CustomExportHelper.make(request, export_type, domain, export_id).custom_export
            if safe_only and not export_object.is_safe:
                return HttpResponseForbidden()
        except ResourceNotFound:
            raise Http404()
        except BadExportConfiguration, e:
            return HttpResponseBadRequest(str(e))

    elif safe_only:
        return HttpResponseForbidden()
    else:
        if not async:
            # this function doesn't support synchronous export without a custom export object
            # if we ever want that (i.e. for HTML Preview) then we just need to give
            # FakeSavedExportSchema a download_data function (called below)
            return HttpResponseBadRequest()
        try:
            export_tag = json.loads(req.get("export_tag", "null") or "null")
        except ValueError:
            return HttpResponseBadRequest()
        assert(export_tag[0] == domain)
        # hack - also filter instances here rather than mess too much with trying to make this
        # look more like a FormExportSchema
        export_class = FakeSavedExportSchema
        if export_type == 'form':
            filter &= SerializableFunction(instances)
            export_class = FakeFormExportSchema

        export_object = export_class(index=export_tag)


    if export_type == 'form':
        _filter = filter
        filter = SerializableFunction(default_form_filter, filter=_filter)

    if not filename:
        filename = export_object.name
    filename += ' ' + date.today().isoformat()

    if async:
        return export_object.export_data_async(
            filter=filter,
            filename=filename,
            previous_export_id=previous_export_id,
            format=format,
            max_column_size=max_column_size,
        )
    else:
        if not next:
            next = export.ExcelExportReport.get_url(domain=domain)
        try:
            resp = export_object.download_data(format, filter=filter, limit=limit)
        except SchemaMismatchException, e:
            rebuild_schemas.delay(export_object.index)
            messages.error(
                request,
                "Sorry, the export failed for %s, please try again later" \
                    % export_object.name
            )
            return HttpResponseRedirect(next)
        if resp:
            return resp
        else:
            messages.error(request, "Sorry, there was no data found for the tag '%s'." % export_object.name)
            return HttpResponseRedirect(next)

@login_or_digest
@require_form_export_permission
@require_GET
def hq_download_saved_export(req, domain, export_id):
    export = SavedBasicExport.get(export_id)
    # quasi-security hack: the first key of the index is always assumed
    # to be the domain
    assert domain == export.configuration.index[0]
    cutoff = datetime.utcnow() - timedelta(days=settings.SAVED_EXPORT_ACCESS_CUTOFF)
    if not export.last_accessed or export.last_accessed < cutoff:
        group_id = req.GET.get('group_export_id')
        if group_id:
            try:
                group_config = HQGroupExportConfiguration.get(group_id)
                assert domain == group_config.domain
                all_config_indices = [schema.index for schema in group_config.all_configs]
                list_index = all_config_indices.index(export.configuration.index)
                schema = next(itertools.islice(group_config.all_export_schemas,
                                               list_index,
                                               list_index+1))
                rebuild_export_async.delay(export.configuration, schema, 'couch')
            except Exception:
                notify_exception(req, 'Failed to rebuild export during download')

    export.last_accessed = datetime.utcnow()
    export.save()
    return couchexport_views.download_saved_export(req, export_id)


@login_or_digest
@require_form_export_permission
@require_POST
def hq_update_saved_export(req, domain):
    group_id = req.POST['group_export_id']
    index = int(req.POST['index'])
    group_config = HQGroupExportConfiguration.get(group_id)
    assert domain == group_config.domain
    config, schema = group_config.all_exports[index]
    rebuild_export(config, schema, 'couch')
    messages.success(req, _('The data for {} has been refreshed!').format(config.name))
    return HttpResponseRedirect(reverse(DataInterfaceDispatcher.name(),
                                        args=[domain, req.POST['report_slug']]))


@login_or_digest
@require_form_export_permission
@require_GET
def export_all_form_metadata(req, domain):
    """
    Export metadata for _all_ forms in a domain.
    """
    format = req.GET.get("format", Format.XLS_2007)
    tmp_path = save_metadata_export_to_tempfile(domain, format=format)

    return export_response(open(tmp_path), format, "%s_forms" % domain)

@login_or_digest
@require_form_export_permission
@require_GET
@datespan_in_request(from_param="startdate", to_param="enddate")
def export_all_form_metadata_async(req, domain):
    datespan = req.datespan if req.GET.get("startdate") and req.GET.get("enddate") else None
    group_id = req.GET.get("group")
    ufilter =  UserTypeFilter.get_user_filter(req)[0]
    users = util.get_all_users_by_domain(
        domain=domain,
        group=group_id,
        user_filter=ufilter,
        simplified=True,
        include_inactive=True
    )
    user_ids = filter(None, [u["user_id"] for u in users])
    format = req.GET.get("format", Format.XLS_2007)
    filename = "%s_forms" % domain

    download = DownloadBase()
    download.set_task(create_metadata_export.delay(
        download.download_id,
        domain,
        format=format,
        filename=filename,
        datespan=datespan,
        user_ids=user_ids,
    ))
    return download.get_start_response()


def touch_saved_reports_views(user, domain):
    """
    Hit the saved reports views so stale=update_after doesn't cause the user to
    see old or deleted data after a change when they next load the reports
    homepage.

    """
    ReportConfig.by_domain_and_owner(domain, user._id, limit=1, stale=False)
    ReportNotification.by_domain_and_owner(domain, user._id, limit=1, stale=False)


class AddSavedReportConfigView(View):
    name = 'add_report_config'

    @method_decorator(login_and_domain_required)
    def post(self, request, domain, *args, **kwargs):
        self.domain = domain

        if not self.saved_report_config_form.is_valid():
            return HttpResponseBadRequest()

        update_config_data = copy(self.saved_report_config_form.cleaned_data)
        del update_config_data['_id']
        update_config_data.update({
            'filters': self.filters,
        })
        for field in self.config.properties().keys():
            if field in update_config_data:
                setattr(self.config, field, update_config_data[field])

        # remove start and end date if the date range is "last xx days"
        if (
            self.saved_report_config_form.cleaned_data['days']
            or self.saved_report_config_form.cleaned_data['date_range'] == 'lastmonth'
        ):
            if "start_date" in self.config:
                delattr(self.config, "start_date")
            if "end_date" in self.config:
                delattr(self.config, "end_date")

        self.config.save()
        ReportsTab.clear_dropdown_cache(request, self.domain)
        touch_saved_reports_views(request.couch_user, self.domain)

        return json_response(self.config)

    @property
    @memoized
    def config(self):
        config = ReportConfig.get_or_create(
            self.saved_report_config_form.cleaned_data['_id']
        )
        if config.owner_id:
            # in case a user maliciously tries to edit another user's config
            assert config.owner_id == self.user_id
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
        filters = copy(self.post_data.get('filters', {}))
        for field in ['startdate', 'enddate']:
            if field in filters:
                del filters[field]
        return filters

    @property
    def post_data(self):
        return json.loads(self.request.body)

    @property
    def user_id(self):
        return self.request.couch_user._id


@login_and_domain_required
@datespan_default
def email_report(request, domain, report_slug, report_type=ProjectReportDispatcher.prefix):
    from dimagi.utils.django.email import send_HTML_email
    from forms import EmailReportForm
    user_id = request.couch_user._id

    form = EmailReportForm(request.GET)
    if not form.is_valid():
        return HttpResponseBadRequest()

    config = ReportConfig()
    # see ReportConfig.query_string()
    object.__setattr__(config, '_id', 'dummy')
    config.name = _("Emailed report")
    config.report_type = report_type

    config.report_slug = report_slug
    config.owner_id = user_id
    config.domain = domain

    config.date_range = 'range'
    config.start_date = request.datespan.computed_startdate.date()
    config.end_date = request.datespan.computed_enddate.date()

    GET = dict(request.GET.iterlists())
    exclude = ['startdate', 'enddate', 'subject', 'send_to_owner', 'notes', 'recipient_emails']
    filters = {}
    for field in GET:
        if not field in exclude:
            filters[field] = GET.get(field)

    config.filters = filters

    body = _render_report_configs(request, [config],
                                  domain,
                                  user_id, request.couch_user,
                                  True,
                                  notes=form.cleaned_data['notes'])[0].content

    subject = form.cleaned_data['subject'] or _("Email report from CommCare HQ")

    if form.cleaned_data['send_to_owner']:
        send_HTML_email(subject, request.couch_user.get_email(), body,
                        email_from=settings.DEFAULT_FROM_EMAIL)

    if form.cleaned_data['recipient_emails']:
        for recipient in form.cleaned_data['recipient_emails']:
            send_HTML_email(subject, recipient, body, email_from=settings.DEFAULT_FROM_EMAIL)

    return HttpResponse()

@login_and_domain_required
@require_http_methods(['DELETE'])
def delete_config(request, domain, config_id):
    try:
        config = ReportConfig.get(config_id)
    except ResourceNotFound:
        raise Http404()

    config.delete()
    ReportsTab.clear_dropdown_cache(request, domain)

    touch_saved_reports_views(request.couch_user, domain)
    return HttpResponse()

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
    return datetime.now(pytz.timezone(Domain._get_by_name(domain)['default_timezone'])).strftime('%z')


def calculate_day(interval, day, day_change):
    if interval == "weekly":
        return (day + day_change) % 7
    elif interval == "monthly":
        return (day - 1 + day_change) % 31 + 1
    return day


@login_and_domain_required
def edit_scheduled_report(request, domain, scheduled_report_id=None,
                          template="reports/edit_scheduled_report.html"):
    from corehq.apps.users.models import WebUser
    from corehq.apps.reports.forms import ScheduledReportForm

    context = {
        'form': None,
        'domain': domain,
        'report': {
            'show': request.couch_user.can_view_reports() or request.couch_user.get_viewable_reports(),
            'slug': None,
            'default_url': reverse('reports_home', args=(domain,)),
            'is_async': False,
            'section_name': ProjectReport.section_name,
        }
    }

    user_id = request.couch_user._id

    configs = [
        c for c in ReportConfig.by_domain_and_owner(domain, user_id)
        if c.report and c.report.emailable
    ]

    if not configs:
        return render(request, template, context)

    display_privacy_disclaimer = any(c.is_configurable_report for c in configs)

    config_choices = [(c._id, c.full_name) for c in configs]

    web_users = WebUser.view('users/web_users_by_domain', reduce=False,
                               key=domain, include_docs=True).all()
    web_user_emails = [u.get_email() for u in web_users]

    if scheduled_report_id:
        instance = ReportNotification.get(scheduled_report_id)
        time_difference = get_timezone_difference(domain)
        (instance.hour, day_change) = recalculate_hour(instance.hour, int(time_difference[:3]), int(time_difference[3:]))
        instance.minute = 0
        if day_change:
            instance.day = calculate_day(instance.interval, instance.day, day_change)

        if instance.owner_id != user_id or instance.domain != domain:
            raise HttpResponseBadRequest()
    else:
        instance = ReportNotification(owner_id=user_id, domain=domain,
                                      config_ids=[], hour=8, minute=0,
                                      send_to_owner=True, recipient_emails=[])

    is_new = instance.new_document
    initial = instance.to_json()
    initial['recipient_emails'] = ', '.join(initial['recipient_emails'])

    kwargs = {'initial': initial}
    args = (
        (display_privacy_disclaimer, request.POST)
        if request.method == "POST"
        else (display_privacy_disclaimer,)
    )
    form = ScheduledReportForm(*args, **kwargs)

    form.fields['config_ids'].choices = config_choices
    form.fields['recipient_emails'].choices = web_user_emails

    form.fields['hour'].help_text = "This scheduled report's timezone is %s (%s GMT)"  % \
                                    (Domain._get_by_name(domain)['default_timezone'],
                                    get_timezone_difference(domain)[:3] + ':' + get_timezone_difference(domain)[3:])


    if request.method == "POST" and form.is_valid():
        for k, v in form.cleaned_data.items():
            setattr(instance, k, v)

        time_difference = get_timezone_difference(domain)
        (instance.hour, day_change) = calculate_hour(instance.hour, int(time_difference[:3]), int(time_difference[3:]))
        instance.minute = int(time_difference[3:])
        if day_change:
            instance.day = calculate_day(instance.interval, instance.day, day_change)

        instance.save()
        ReportsTab.clear_dropdown_cache(request, domain)
        if is_new:
            messages.success(request, "Scheduled report added!")
        else:
            messages.success(request, "Scheduled report updated!")

        touch_saved_reports_views(request.couch_user, domain)
        return HttpResponseRedirect(reverse('reports_home', args=(domain,)))

    context['form'] = form
    context['day_value'] = getattr(instance, "day", 1)
    context['weekly_day_options'] = ReportNotification.day_choices()
    context['monthly_day_options'] = [(i, i) for i in range(1, 32)]
    if is_new:
        context['form_action'] = "Create a new"
        context['report']['title'] = "New Scheduled Report"
    else:
        context['form_action'] = "Edit"
        context['report']['title'] = "Edit Scheduled Report"

    return render(request, template, context)

@login_and_domain_required
@require_POST
def delete_scheduled_report(request, domain, scheduled_report_id):
    user_id = request.couch_user._id
    try:
        rep = ReportNotification.get(scheduled_report_id)
    except ResourceNotFound:
        # was probably already deleted by a fast-clicker.
        pass
    else:
        if user_id != rep.owner._id:
            return HttpResponseBadRequest()

        rep.delete()
        messages.success(request, "Scheduled report deleted!")
    return HttpResponseRedirect(reverse("reports_home", args=(domain,)))

@login_and_domain_required
def send_test_scheduled_report(request, domain, scheduled_report_id):
    from corehq.apps.reports.tasks import send_report
    from corehq.apps.users.models import CouchUser, CommCareUser, WebUser

    user_id = request.couch_user._id

    notification = ReportNotification.get(scheduled_report_id)
    try:
        user = WebUser.get_by_user_id(user_id, domain)
    except CouchUser.AccountTypeError:
        user = CommCareUser.get_by_user_id(user_id, domain)

    try:
        send_report.delay(notification._id)
    except Exception, e:
        import logging
        logging.exception(e)
        messages.error(request, "An error occured, message unable to send")
    else:
        messages.success(request, "Test message sent to %s" % user.get_email())

    return HttpResponseRedirect(reverse("reports_home", args=(domain,)))


def get_scheduled_report_response(couch_user, domain, scheduled_report_id,
                                  email=True, attach_excel=False):
    """
    This function somewhat confusingly returns a tuple of: (response, excel_files)
    If attach_excel is false, excel_files will always be an empty list.
    """
    # todo: clean up this API?
    from django.http import HttpRequest

    request = HttpRequest()
    request.couch_user = couch_user
    request.user = couch_user.get_django_user()
    request.domain = domain
    request.couch_user.current_domain = domain

    notification = ReportNotification.get(scheduled_report_id)
    return _render_report_configs(request, notification.configs,
                                  notification.domain,
                                  notification.owner_id,
                                  couch_user,
                                  email, attach_excel=attach_excel)

def _render_report_configs(request, configs, domain, owner_id, couch_user, email, notes=None, attach_excel=False):
    from dimagi.utils.web import get_url_base

    report_outputs = []
    excel_attachments = []
    format = Format.from_format(request.GET.get('format') or Format.XLS_2007)
    for config in configs:
        content, excel_file = config.get_report_content(attach_excel=attach_excel)
        if excel_file:
            excel_attachments.append({
                'title': config.full_name + "." + format.extension,
                'file_obj': excel_file,
                'mimetype': format.mimetype
            })
        report_outputs.append({
            'title': config.full_name,
            'url': config.url,
            'content': content,
            'description': config.description,
        })

    date_range = config.get_date_range()
    return render(request, "reports/report_email.html", {
        "reports": report_outputs,
        "domain": domain,
        "couch_user": owner_id,
        "DNS_name": get_url_base(),
        "owner_name": couch_user.full_name or couch_user.get_email(),
        "email": email,
        "notes": notes,
        "startdate": date_range["startdate"] if date_range else "",
        "enddate": date_range["enddate"] if date_range else "",
    }), excel_attachments

@login_and_domain_required
@permission_required("is_superuser")
def view_scheduled_report(request, domain, scheduled_report_id):
    return get_scheduled_report_response(
        request.couch_user, domain, scheduled_report_id, email=False
    )[0]


@require_case_view_permission
@login_and_domain_required
@require_GET
def case_details(request, domain, case_id):
    timezone = get_timezone_for_user(request.couch_user, domain)

    try:
        case = get_document_or_404(CommCareCase, domain, case_id)
    except Http404:
        messages.info(request, "Sorry, we couldn't find that case. If you think this is a mistake please report an issue.")
        return HttpResponseRedirect(CaseListReport.get_url(domain=domain))

    try:
        owner_name = CommCareUser.get_by_user_id(case.owner_id, domain).raw_username
    except Exception:
        try:
            owning_group = Group.get(case.owner_id)
            owner_name = owning_group.display_name if owning_group.domain == domain else ''
        except Exception:
            owner_name = None

    try:
        username = CommCareUser.get_by_user_id(case.user_id, domain).raw_username
    except Exception:
        username = None

    return render(request, "reports/reportdata/case_details.html", {
        "domain": domain,
        "case_id": case_id,
        "case": case,
        "username": username,
        "owner_name": owner_name,
        "slug": CaseListReport.slug,
        "report": dict(
            name=case_inline_display(case),
            slug=CaseListReport.slug,
            is_async=False,
        ),
        "layout_flush_content": True,
        "timezone": timezone,
        "case_display_options": {
            "display": request.project.get_case_display(case),
            "timezone": timezone,
            "get_case_url": lambda case_id: absolute_reverse(case_details, args=[domain, case_id]),
            "show_transaction_export": toggles.STOCK_TRANSACTION_EXPORT.enabled(request.user.username),
        },
        "show_case_rebuild": toggles.CASE_REBUILD.enabled(request.user.username),
    })


@login_and_domain_required
@require_GET
def case_attachments(request, domain, case_id):
    if not can_view_attachments(request):
        return HttpResponseForbidden(_("You don't have permission to access this page."))

    case = get_document_or_404(CommCareCase, domain, case_id)
    return render(request, 'reports/reportdata/case_attachments.html',
                  {'domain': domain, 'case': case})


@require_case_view_permission
@login_and_domain_required
@require_GET
def case_xml(request, domain, case_id):
    case = get_document_or_404(CommCareCase, domain, case_id)
    version = request.GET.get('version', V2)
    return HttpResponse(case.to_xml(version), content_type='text/xml')


@require_case_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def rebuild_case_view(request, domain, case_id):
    case = get_document_or_404(CommCareCase, domain, case_id)
    rebuild_case(case_id)
    messages.success(request, _(u'Case %s was rebuilt from its forms.' % case.name))
    return HttpResponseRedirect(reverse('case_details', args=[domain, case_id]))


@require_case_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def close_case_view(request, domain, case_id):
    case = get_document_or_404(CommCareCase, domain, case_id)
    if case.closed:
        messages.info(request, u'Case {} is already closed.'.format(case.name))
    else:
        form_id = close_case(case_id, domain, request.couch_user)
        msg = _(u'''Case {name} has been closed.
            <a href="javascript:document.getElementById('{html_form_id}').submit();">Undo</a>.
            You can also reopen the case in the future by archiving the last form in the case history.
            <form id="{html_form_id}" action="{url}" method="POST">
                <input type="hidden" name="closing_form" value="{xform_id}" />
            </form>
        '''.format(
            name=case.name,
            html_form_id='undo-close-case',
            xform_id=form_id,
            url=reverse('undo_close_case', args=[domain, case_id]),
        ))
        messages.success(request, mark_safe(msg), extra_tags='html')
    return HttpResponseRedirect(reverse('case_details', args=[domain, case_id]))


@require_case_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def undo_close_case_view(request, domain, case_id):
    case = get_document_or_404(CommCareCase, domain, case_id)
    if not case.closed:
        messages.info(request, u'Case {} is not closed.'.format(case.name))
    else:
        closing_form_id = request.POST['closing_form']
        assert closing_form_id in case.xform_ids
        form = XFormInstance.get(closing_form_id)
        form.archive(user=request.couch_user._id)
        messages.success(request, u'Case {} has been reopened.'.format(case.name))
    return HttpResponseRedirect(reverse('case_details', args=[domain, case_id]))


@require_case_view_permission
@login_and_domain_required
@require_GET
def export_case_transactions(request, domain, case_id):
    case = get_document_or_404(CommCareCase, domain, case_id)
    products_by_id = dict(SQLProduct.objects.filter(domain=domain).values_list('product_id', 'name'))

    headers = [
        _('case id'),
        _('case name'),
        _('section'),
        _('date'),
        _('product_id'),
        _('product_name'),
        _('transaction amount'),
        _('type'),
        _('ending balance'),
    ]

    def _make_row(transaction):
        return [
            transaction.case_id,
            case.name,
            transaction.section_id,
            transaction.report.date if transaction.report_id else '',
            transaction.product_id,
            products_by_id.get(transaction.product_id, _('unknown product')),
            transaction.quantity,
            transaction.type,
            transaction.stock_on_hand,
        ]

    query_set = StockTransaction.objects.select_related('report')\
        .filter(case_id=case_id).order_by('section_id', 'report__date')

    formatted_table = [
        [
            'stock transactions',
            [headers] + [_make_row(txn) for txn in query_set]
        ]
    ]
    tmp = StringIO()
    export_from_tables(formatted_table, tmp, 'xlsx')
    return export_response(tmp, 'xlsx', '{}-stock-transactions'.format(case.name))


def generate_case_export_payload(domain, include_closed, format, group, user_filter, process=None):
    """
    Returns a FileWrapper object, which only the file backend in django-soil supports

    """
    status = 'all' if include_closed else 'open'
    case_ids = CommCareCase.get_all_cases(domain, status=status, wrapper=lambda r: r['id'])

    class stream_cases(object):
        def __init__(self, all_case_ids):
            self.all_case_ids = all_case_ids

        def __iter__(self):
            for case_ids in chunked(self.all_case_ids, 500):
                for case in wrapped_docs(CommCareCase, case_ids):
                    yield case

        def __len__(self):
            return len(self.all_case_ids)

    # todo deal with cached user dict here
    group = Group.get(group) if group else None
    users = get_all_users_by_domain(
        domain,
        group=group,
        user_filter=user_filter,
        include_inactive=True
    )
    groups = Group.get_case_sharing_groups(domain)

    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, 'wb') as file:
        workbook = WorkBook(file, format)
        export_cases(
            domain,
            stream_cases(case_ids),
            workbook,
            filter_group=group,
            users=users,
            all_groups=groups,
            process=process
        )
        export_users(users, workbook)
        workbook.close()
    return FileWrapper(open(path))

@login_or_digest
@require_case_export_permission
@require_GET
def download_cases(request, domain):
    include_closed = json.loads(request.GET.get('include_closed', 'false'))
    try:
        format = Format.from_format(request.GET.get('format') or Format.XLS_2007)
    except URLError as e:
        return HttpResponseBadRequest(e.reason)
    group = request.GET.get('group', None)
    user_filter, _ = UserTypeFilter.get_user_filter(request)

    async = request.GET.get('async') == 'true'

    kwargs = {
        'domain': domain,
        'include_closed': include_closed,
        'format': format,
        'group': group,
        'user_filter': user_filter,
    }
    payload_func = SerializableFunction(generate_case_export_payload, **kwargs)
    content_disposition = 'attachment; filename="{domain}_data.{ext}"'.format(domain=domain, ext=format.extension)
    mimetype = "%s" % format.mimetype

    def generate_payload(payload_func):
        if async:
            download = DownloadBase()
            a_task = prepare_download.delay(download.download_id, payload_func,
                                            content_disposition, mimetype)
            download.set_task(a_task)
            return download.get_start_response()
        else:
            payload = payload_func()
            response = HttpResponse(payload)
            response['Content-Type'] = mimetype
            response['Content-Disposition'] = content_disposition
            return response

    return generate_payload(payload_func)


def _get_form_context(request, domain, instance_id):
    timezone = get_timezone_for_user(request.couch_user, domain)
    instance = _get_form_or_404(instance_id)
    try:
        assert domain == instance.domain
    except AssertionError:
        raise Http404()

    display = request.project.get_form_display(instance)
    context = {
        "domain": domain,
        "display": display,
        "timezone": timezone,
        "instance": instance,
        "user": request.couch_user,
        "request": request,
    }
    context['form_render_options'] = context
    return context


def _get_form_or_404(id):
    # maybe this should be a more general utility a-la-django's get_object_or_404
    try:
        xform_json = XFormInstance.get_db().get(id)
    except ResourceNotFound:
        raise Http404()

    doc_type = doc_types().get(xform_json.get('doc_type'))
    if not doc_type:
        raise Http404()

    return doc_type.wrap(xform_json)


@require_form_view_permission
@login_and_domain_required
@require_GET
def form_data(request, domain, instance_id):
    context = _get_form_context(request, domain, instance_id)
    instance = context['instance']
    context['form_meta'] = FormType(domain, instance.xmlns, instance.app_id).metadata
    try:
        form_name = context['instance'].form["@name"]
    except KeyError:
        form_name = "Untitled Form"

    context.update({
        "slug": inspect.SubmitHistory.slug,
        "form_name": form_name,
        "form_received_on": context['instance'].received_on
    })

    return render(request, "reports/reportdata/form_data.html", context)


@require_form_view_permission
@login_and_domain_required
@require_GET
def case_form_data(request, domain, case_id, xform_id):
    context = _get_form_context(request, domain, xform_id)
    context['case_id'] = case_id
    context['side_pane'] = True
    return HttpResponse(render_form(context['instance'], domain, options=context))


@require_form_view_permission
@login_and_domain_required
@require_GET
def download_form(request, domain, instance_id):
    instance = _get_form_or_404(instance_id)
    assert(domain == instance.domain)
    return couchforms_views.download_form(request, instance_id)

@login_or_digest
@require_form_view_permission
@require_GET
def download_attachment(request, domain, instance_id):
    attachment = request.GET.get('attachment', False)
    if not attachment:
        return HttpResponseBadRequest("Invalid attachment.")
    instance = _get_form_or_404(instance_id)
    assert(domain == instance.domain)
    return couchforms_views.download_attachment(request, instance_id, attachment)


@require_form_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def archive_form(request, domain, instance_id):
    instance = _get_form_or_404(instance_id)
    assert instance.domain == domain
    if instance.doc_type == "XFormInstance":
        instance.archive(user=request.couch_user._id)
        notif_msg = _("Form was successfully archived.")
    elif instance.doc_type == "XFormArchived":
        notif_msg = _("Form was already archived.")
    else:
        notif_msg = _("Can't archive documents of type %s. How did you get here??") % instance.doc_type

    params = {
        "notif": notif_msg,
        "undo": _("Undo"),
        "url": reverse('unarchive_form', args=[domain, instance_id]),
        "id": "restore-%s" % instance_id
    }
    msg_template = u"""{notif} <a href="javascript:document.getElementById('{id}').submit();">{undo}</a>
        <form id="{id}" action="{url}" method="POST"></form>""" if instance.doc_type == "XFormArchived" \
        else u'%(notif)s'
    msg = msg_template.format(**params)
    messages.success(request, mark_safe(msg), extra_tags='html')

    redirect = request.META.get('HTTP_REFERER')
    if not redirect:
        redirect = inspect.SubmitHistory.get_url(domain)

    # check if referring URL was a case detail view, then make sure
    # the case still exists before redirecting.
    template = reverse('case_details', args=[domain, 'fake_case_id'])
    template = template.replace('fake_case_id', '([^/]*)')
    case_id = re.findall(template, redirect)
    if case_id:
        try:
            case = CommCareCase.get(case_id[0])
            if case._doc['doc_type'] == 'CommCareCase-Deleted':
                raise ResourceNotFound
        except ResourceNotFound:
            redirect = reverse('project_report_dispatcher', args=[domain, 'case_list'])

    return HttpResponseRedirect(redirect)


@require_form_view_permission
@require_permission(Permissions.edit_data)
def unarchive_form(request, domain, instance_id):
    instance = _get_form_or_404(instance_id)
    assert instance.domain == domain
    if instance.doc_type == "XFormArchived":
        instance.unarchive(user=request.couch_user._id)
    else:
        assert instance.doc_type == "XFormInstance"
    messages.success(request, _("Form was successfully restored."))

    redirect = request.META.get('HTTP_REFERER')
    if not redirect:
        redirect = reverse('render_form_data', args=[domain, instance_id])
    return HttpResponseRedirect(redirect)


@require_form_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def resave_form(request, domain, instance_id):
    instance = _get_form_or_404(instance_id)
    assert instance.domain == domain
    XFormInstance.get_db().save_doc(instance.to_json())
    messages.success(request, _("Form was successfully resaved. It should reappear in reports shortly."))
    return HttpResponseRedirect(reverse('render_form_data', args=[domain, instance_id]))


# Weekly submissions by xmlns
def mk_date_range(start=None, end=None, ago=timedelta(days=7), iso=False):
    if isinstance(end, basestring):
        end = parse_date(end)
    if isinstance(start, basestring):
        start = parse_date(start)
    if not end:
        end = datetime.utcnow()
    if not start:
        start = end - ago
    if iso:
        return json_format_datetime(start), json_format_datetime(end)
    else:
        return start, end


@login_and_domain_required
@permission_required("is_superuser")
def clear_report_caches(request, domain):
    print "CLEARING CACHE FOR DOMAIN", domain
    print "ALL CACHES", cache.all()
    return HttpResponse("TESTING")


@require_case_view_permission
@login_and_domain_required
@require_GET
def export_report(request, domain, export_hash, format):
    cache = get_redis_client()

    if cache.exists(export_hash):
        if format in Format.VALID_FORMATS:
            content = cache.get(export_hash)
            file = ContentFile(content)
            response = HttpResponse(file, Format.FORMAT_DICT[format])
            response['Content-Length'] = file.size
            response['Content-Disposition'] = 'attachment; filename="{filename}.{extension}"'.format(
                filename=export_hash,
                extension=Format.FORMAT_DICT[format]['extension']
            )
            return response
        else:
            return HttpResponseNotFound(_("We don't support this format"))
    else:
        return HttpResponseNotFound(_("That report was not found. Please remember"
                                      " that download links expire after 24 hours."))


def find_question_id(form, value):
    for k, v in form.iteritems():
        if isinstance(v, dict):
            ret = find_question_id(v, value)
            if ret:
                return [k] + ret
        else:
            if v == value:
                return [k]

    return None


@require_form_view_permission
@login_and_domain_required
@require_GET
def form_multimedia_export(request, domain):
    try:
        xmlns = request.GET["xmlns"]
        startdate = request.GET["startdate"]
        enddate = request.GET["enddate"]
        enddate = json_format_date(string_to_datetime(enddate) + timedelta(days=1))
        app_id = request.GET.get("app_id", None)
        export_id = request.GET.get("export_id", None)
        zip_name = request.GET.get("name", None)
    except (KeyError, ValueError):
        return HttpResponseBadRequest()

    def filename(form_info, question_id, extension):
        fname = u"%s-%s-%s-%s%s"
        if form_info['cases']:
            fname = u'-'.join(form_info['cases']) + u'-' + fname
        return fname % (form_info['name'],
                        unidecode(question_id),
                        form_info['user'],
                        form_info['id'], extension)

    case_ids = set()

    def extract_form_info(form, properties=None, case_ids=case_ids):
        unknown_number = 0
        meta = form['form'].get('meta', dict())
        # get case ids
        case_blocks = extract_case_blocks(form)
        cases = {c['@case_id'] for c in case_blocks}
        case_ids |= cases

        form_info = {
            'form': form,
            'attachments': list(),
            'name': form['form'].get('@name', 'unknown form'),
            'user': meta.get('username', 'unknown_user'),
            'cases': cases,
            'id': form['_id']
        }
        for k, v in form['_attachments'].iteritems():
            if v['content_type'] == 'text/xml':
                continue
            try:
                question_id = unicode(u'-'.join(find_question_id(form['form'], k)))
            except TypeError:
                question_id = unicode(u'unknown' + unicode(unknown_number))
                unknown_number += 1

            if not properties or question_id in properties:
                extension = unicode(os.path.splitext(k)[1])
                form_info['attachments'].append({
                    'size': v['length'],
                    'name': k,
                    'question_id': question_id,
                    'extension': extension,
                    'timestamp': parse(form['received_on']).timetuple(),
                })

        return form_info

    key = [domain, app_id, xmlns]
    form_ids = {f['id'] for f in XFormInstance.get_db().view("attachments/attachments",
                                         start_key=key + [startdate],
                                         end_key=key + [enddate, {}],
                                         reduce=False)}

    properties = set()
    if export_id:
        schema = FormExportSchema.get(export_id)
        for table in schema.tables:
            # - in question id is replaced by . in excel exports
            properties |= {c.display.replace('.', '-') for c in table.columns}

    if not app_id:
        zip_name = 'Unrelated Form'
    forms_info = list()
    for form in iter_docs(XFormInstance.get_db(), form_ids):
        if not zip_name:
            zip_name = unidecode(form['form'].get('@name', 'unknown form'))
        forms_info.append(extract_form_info(form, properties))

    # get case names
    case_id_to_name = {c: c for c in case_ids}
    for case in iter_docs(CommCareCase.get_db(), case_ids):
        if case['name']:
            case_id_to_name[case['_id']] = case['name']

    stream_file = cStringIO.StringIO()
    size = 22  # overhead for a zipfile
    zf = zipfile.ZipFile(stream_file, mode='w', compression=zipfile.ZIP_STORED)
    for form_info in forms_info:
        f = XFormInstance.wrap(form_info['form'])
        form_info['cases'] = {case_id_to_name[case_id] for case_id in form_info['cases']}
        for a in form_info['attachments']:
            fname = filename(form_info, a['question_id'], a['extension'])
            zi = zipfile.ZipInfo(fname, a['timestamp'])
            zf.writestr(zi, f.fetch_attachment(a['name'], stream=True).read())
            size += a['size'] + 88 + 2 * len(fname)  # zip file overhead

    zf.close()

    response = HttpResponse(stream_file.getvalue(), mimetype="application/zip")
    response['Content-Length'] = size
    response['Content-Disposition'] = 'attachment; filename=%s.zip' % zip_name
    return response
