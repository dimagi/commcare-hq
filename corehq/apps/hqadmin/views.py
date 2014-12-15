import HTMLParser
import json
import logging
import socket
import time
from datetime import timedelta, datetime, date
from copy import deepcopy
from collections import defaultdict
from StringIO import StringIO
import dateutil
from django.utils.datastructures import SortedDict

from django.views.decorators.http import require_POST, require_GET
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.core import management, cache
from django.core.urlresolvers import reverse
from django.shortcuts import render, redirect
from django.views.decorators.cache import cache_page
from django.views.generic import FormView
from django.template.defaultfilters import yesno
from django.utils import html
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.template.loader import render_to_string
from django.http import (
    HttpResponseRedirect,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
    Http404,
)
from restkit import Resource

from casexml.apps.case.models import CommCareCase
from corehq.apps.callcenter.indicator_sets import CallCenterIndicators
from couchdbkit import ResourceNotFound
from corehq.apps.hqcase.utils import get_case_by_domain_hq_user_id
from corehq.apps.ota.tasks import prime_restore
from couchexport.export import export_raw, export_from_tables
from couchexport.shortcuts import export_response
from couchexport.models import Format
from couchforms.models import XFormInstance
from phonelog.utils import device_users_by_xform
from phonelog.models import DeviceReportEntry
from phonelog.reports import TAGS
from pillowtop import get_all_pillows_json, get_pillow_by_name

from corehq.apps.app_manager.models import ApplicationBase
from corehq.apps.app_manager.util import get_settings_values
from corehq.apps.es.cases import CaseES
from corehq.apps.es.domains import DomainES
from corehq.apps.es.forms import FormES
from corehq.apps.hqadmin.history import get_recent_changes, download_changes
from corehq.apps.hqadmin.models import HqDeploy
from corehq.apps.hqadmin.forms import EmailForm, BrokenBuildsForm, PrimeRestoreCacheForm
from corehq.apps.builds.models import CommCareBuildConfig, BuildSpec
from corehq.apps.domain.decorators import require_superuser, require_superuser_or_developer
from corehq.apps.domain.models import Domain
from corehq.apps.es.users import UserES
from corehq.apps.hqadmin.escheck import check_es_cluster_health, check_xform_es_index, check_reportcase_es_index, check_case_es_index, check_reportxform_es_index
from corehq.apps.hqadmin.system_info.checks import check_redis, check_rabbitmq, check_celery_health, check_memcached
from corehq.apps.hqadmin.reporting.reports import (
    get_project_spaces,
    get_stats_data,
)
from corehq.apps.ota.views import get_restore_response, get_restore_params
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader, DTSortType
from corehq.apps.reports.graph_models import Axis, LineChart
from corehq.apps.reports.util import make_form_couch_key, format_datatables_data
from corehq.apps.sms.models import SMSLog
from corehq.apps.sofabed.models import FormData
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.users.util import format_username
from corehq.db import Session
from corehq.elastic import parse_args_for_es, ES_URLS, run_query
from dimagi.utils.couch.database import get_db, is_bigcouch
from dimagi.utils.decorators.datespan import datespan_in_request
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.parsing import json_format_datetime, string_to_datetime
from dimagi.utils.web import json_response, get_url_base
from dimagi.utils.excel import WorkbookJSONReader
from dimagi.utils.decorators.view import get_file
from dimagi.utils.django.email import send_HTML_email

from .multimech import GlobalConfig
from soil import DownloadBase


@require_superuser
def default(request):
    return HttpResponseRedirect(reverse('admin_report_dispatcher', args=('domains',)))

datespan_default = datespan_in_request(
    from_param="startdate",
    to_param="enddate",
    default_days=30,
)


def get_rabbitmq_management_url():
    if settings.BROKER_URL.startswith('amqp'):
        amqp_parts = settings.BROKER_URL.replace('amqp://','').split('/')
        mq_management_url = amqp_parts[0].replace('5672', '15672')
        return "http://%s" % mq_management_url.split('@')[-1]
    else:
        return None

def get_hqadmin_base_context(request):
    return {
        "domain": None,
    }


@require_superuser
def active_users(request):
    keys = []
    number_threshold = 15
    date_threshold_days_ago = 90
    date_threshold = json_format_datetime(datetime.utcnow() - timedelta(days=date_threshold_days_ago))
    key = make_form_couch_key(None, user_id="")
    for line in get_db().view("reports_forms/all_forms",
        startkey=key,
        endkey=key+[{}],
        group_level=3):
        if line['value'] >= number_threshold:
            keys.append(line["key"])

    final_count = defaultdict(int)

    def is_valid_user_id(user_id):
        if not user_id: return False
        try:
            get_db().get(user_id)
            return True
        except Exception:
            return False

    for time_type, domain, user_id in keys:
        if get_db().view("reports_forms/all_forms",
            reduce=False,
            startkey=[time_type, domain, user_id, date_threshold],
            limit=1):
            if True or is_valid_user_id(user_id):
                final_count[domain] += 1

    return json_response({"break_down": final_count, "total": sum(final_count.values())})

@require_superuser
def global_report(request, template="hqadmin/global.html", as_export=False):

    def _flot_format(result):
        return int(datetime(year=result['key'][0], month=result['key'][1], day=1).strftime("%s"))*1000

    def _export_format(result):
        return datetime(year=result['key'][0], month=result['key'][1], day=1).strftime("%Y-%m-%d")

    context = get_hqadmin_base_context(request)

    def _metric(name):
        counts = []
        for result in get_db().view("hqadmin/%ss_over_time" % name, group_level=2):
            if not result or not result.has_key('key') or not result.has_key('value'): continue
            if result['key'][0] and int(result['key'][0]) >= 2010 and \
               (int(result['key'][0]) < datetime.utcnow().year or
                (int(result['key'][0]) == datetime.utcnow().year and
                 int(result['key'][1]) <= datetime.utcnow().month)):
                counts.append([_export_format(result) if as_export else _flot_format(result), result['value']])
        context['%s_counts' % name] = counts
        counts_int = deepcopy(counts)
        for i in range(1, len(counts_int)):
            if isinstance(counts_int[i][1], int):
                counts_int[i][1] += counts_int[i-1][1]
        context['%s_counts_int' % name] = counts_int

    standard_metrics = ["case", "form", "user"]
    for m in standard_metrics:
        _metric(m)

    def _active_metric(name):
        dates = {}
        for result in get_db().view("hqadmin/%ss_over_time" % name, group=True):
            if not result or not result.has_key('key') or not result.has_key('value'): continue
            if result['key'][0] and int(result['key'][0]) >= 2010 and\
               (int(result['key'][0]) < datetime.utcnow().year or
                (int(result['key'][0]) == datetime.utcnow().year and
                 int(result['key'][1]) <= datetime.utcnow().month)):
                date = _export_format(result) if as_export else _flot_format(result)
                if not date in dates:
                    dates[date] = set([result['key'][2]])
                else:
                    dates[date].update([result['key'][2]])
        datelist = [[date, dates[date]] for date in sorted(dates.keys())]
        domainlist = [[x[0], len(x[1])] for x in datelist]
        domainlist_int = deepcopy(datelist)
        for i in range(1, len(domainlist_int)):
            domainlist_int[i][1] = list(set(domainlist_int[i-1][1]).union(domainlist_int[i][1]))
        domainlist_int = [[x[0], len(x[1])] for x in domainlist_int]
        context['%s_counts' % name] = domainlist
        context['%s_counts_int' % name] = domainlist_int

    active_metrics = ["active_domain", "active_user"]
    for a in active_metrics:
        _active_metric(a)


    if as_export:
        all_metrics = standard_metrics + active_metrics
        format = request.GET.get("format", "xls")
        tables = []
        for metric_name in all_metrics:
            table = context.get('%s_counts' % metric_name, [])
            table = [["%s" % item[0], "%d" % item[1]] for item in table]
            table.reverse()
            table.append(["date", "%s count" % metric_name])
            table.reverse()

            table_int = context.get('%s_counts_int' % metric_name, [])
            table_int = [["%s" % item[0], "%d" % item[1]] for item in table_int]
            table_int.reverse()
            table_int.append(["date", "%s count, cumulative" % metric_name])
            table_int.reverse()

            tables.append(["%s counts" % metric_name, table])
            tables.append(["%s cumulative" % metric_name, table_int])
        temp = StringIO()
        export_from_tables(tables, temp, format)
        return export_response(temp, format, "GlobalReport")

    context['hide_filters'] = True

    return render(request, template, context)

@require_superuser
def commcare_version_report(request, template="hqadmin/commcare_version.html"):
    apps = get_db().view('app_manager/applications_brief').all()
    menu = CommCareBuildConfig.fetch().menu
    builds = [item.build.to_string() for item in menu]
    by_build = dict([(item.build.to_string(), {"label": item.label, "apps": []}) for item in menu])

    for app in apps:
        app = app['value']
        app['id'] = app['_id']
        if app.get('build_spec'):
            build_spec = BuildSpec.wrap(app['build_spec'])
            build = build_spec.to_string()
            if by_build.has_key(build):
                by_build[build]['apps'].append(app)
            else:
                by_build[build] = {"label": build_spec.get_label(), "apps": [app]}
                builds.append(build)

    tables = []
    for build in builds:
        by_build[build]['build'] = build
        tables.append(by_build[build])
    context = get_hqadmin_base_context(request)
    context.update({'tables': tables})
    context['hide_filters'] = True
    return render(request, template, context)


@cache_page(60*5)
def _cacheable_domain_activity_report(request):
    landmarks = json.loads(request.GET.get('landmarks') or "[7, 30, 90]")
    landmarks.sort()
    now = datetime.utcnow()
    dates = []
    for landmark in landmarks:
        dates.append(now - timedelta(days=landmark))
    domains = [{'name': domain.name, 'display_name': domain.display_name()} for domain in Domain.get_all()]

    for domain in domains:
        domain['users'] = dict([(user.user_id, {'raw_username': user.raw_username}) for user in CommCareUser.by_domain(domain['name'])])
        if not domain['users']:
            continue
        key = make_form_couch_key(domain['name'])
        forms = [r['value'] for r in get_db().view('reports_forms/all_forms',
            reduce=False,
            startkey=key+[json_format_datetime(dates[-1])],
            endkey=key+[json_format_datetime(now)],
        ).all()]
        domain['user_sets'] = [dict() for landmark in landmarks]

        for form in forms:
            user_id = form.get('user_id')
            try:
                time = string_to_datetime(form['submission_time']).replace(tzinfo = None)
            except ValueError:
                continue
            if user_id in domain['users']:
                for i, date in enumerate(dates):
                    if time > date:
                        domain['user_sets'][i][user_id] = domain['users'][user_id]

    return HttpResponse(json.dumps({'domains': domains, 'landmarks': landmarks}))

@require_superuser
def domain_activity_report(request, template="hqadmin/domain_activity_report.html"):
    context = get_hqadmin_base_context(request)
    context.update(json.loads(_cacheable_domain_activity_report(request).content))

    context['layout_flush_content'] = True
    headers = DataTablesHeader(
        DataTablesColumn("Domain")
    )
    for landmark in context['landmarks']:
        headers.add_column(DataTablesColumn("Last %s Days" % landmark))
    headers.add_column(DataTablesColumn("All Users"))
    context["headers"] = headers
    context["aoColumns"] = headers.render_aoColumns
    return render(request, template, context)


@datespan_default
@require_superuser
def message_log_report(request):
    show_dates = True
    datespan = request.datespan
    domains = Domain.get_all()

    for dom in domains:
        dom.sms_incoming = SMSLog.count_incoming_by_domain(dom.name, datespan.startdate_param, datespan.enddate_param)
        dom.sms_outgoing = SMSLog.count_outgoing_by_domain(dom.name, datespan.startdate_param, datespan.enddate_param)
        dom.sms_total = SMSLog.count_by_domain(dom.name, datespan.startdate_param, datespan.enddate_param)

    context = get_hqadmin_base_context(request)

    headers = DataTablesHeader(
        DataTablesColumn("Domain"),
        DataTablesColumn("Incoming Messages", sort_type=DTSortType.NUMERIC),
        DataTablesColumn("Outgoing Messages", sort_type=DTSortType.NUMERIC),
        DataTablesColumn("Total Messages", sort_type=DTSortType.NUMERIC)
    )
    context["headers"] = headers
    context["aoColumns"] = headers.render_aoColumns

    context.update({
        "domains": domains,
        "show_dates": show_dates,
        "datespan": datespan
    })

    context['layout_flush_content'] = True
    return render(request, "hqadmin/message_log_report.html", context)

def _get_emails():
    return [r['key'] for r in get_db().view('hqadmin/emails').all()]

@require_superuser
def emails(request):
    email_list = _get_emails()
    return HttpResponse('"' + '", "'.join(email_list) + '"')

@datespan_default
@require_superuser
def submissions_errors(request, template="hqadmin/submissions_errors_report.html"):
    show_dates = "true"
    datespan = request.datespan
    domains = Domain.get_all()

    rows = []
    for domain in domains:
        key = ["active", domain.name]
        data = get_db().view('users/by_domain',
            startkey=key,
            endkey=key+[{}],
            reduce=True
        ).all()
        num_active_users = data[0].get('value', 0) if data else 0

        key = make_form_couch_key(domain.name)
        data = get_db().view('reports_forms/all_forms',
            startkey=key+[datespan.startdate_param_utc],
            endkey=key+[datespan.enddate_param_utc, {}],
            reduce=True
        ).all()
        num_forms_submitted = data[0].get('value', 0) if data else 0

        phonelogs = DeviceReportEntry.objects.filter(domain__exact=domain.name,
            date__range=[datespan.startdate_param_utc, datespan.enddate_param_utc])
        num_errors = phonelogs.filter(type__in=TAGS["error"]).count()
        num_warnings = phonelogs.filter(type__in=TAGS["warning"]).count()

        rows.append(dict(domain=domain.name,
                        active_users=num_active_users,
                        submissions=num_forms_submitted,
                        errors=num_errors,
                        warnings=num_warnings))

    context = get_hqadmin_base_context(request)
    context.update({
        "show_dates": show_dates,
        "datespan": datespan,
        "layout_flush_content": True,
        "rows": rows
    })

    headers = DataTablesHeader(
        DataTablesColumn("Domain"),
        DataTablesColumn("Active Users", sort_type=DTSortType.NUMERIC),
        DataTablesColumn("Forms Submitted", sort_type=DTSortType.NUMERIC),
        DataTablesColumn("Errors", sort_type=DTSortType.NUMERIC),
        DataTablesColumn("Warnings", sort_type=DTSortType.NUMERIC)
    )
    context["headers"] = headers
    context["aoColumns"] = headers.render_aoColumns

    return render(request, template, context)


@require_superuser
def mobile_user_reports(request):
    template = "hqadmin/mobile_user_reports.html"
    _device_users_by_xform = memoized(device_users_by_xform)
    rows = []

    logs = DeviceReportEntry.objects.filter(type__exact="user-report").order_by('domain')
    for log in logs:
        seconds_since_epoch = int(time.mktime(log.date.timetuple()) * 1000)
        rows.append(dict(domain=log.domain,
                         time=format_datatables_data(text=log.date, sort_key=seconds_since_epoch),
                         user=log.username,
                         device_users=_device_users_by_xform(log.xform_id),
                         message=log.msg,
                         version=(log.app_version or 'unknown').split(' ')[0],
                         detailed_version=html.escape(log.app_version or 'unknown'),
                         report_id=log.xform_id))

    headers = DataTablesHeader(
        DataTablesColumn(_("View Form")),
        DataTablesColumn(_("Domain")),
        DataTablesColumn(_("Time"), sort_type=DTSortType.NUMERIC),
        DataTablesColumn(_("User"), sort_type=DTSortType.NUMERIC),
        DataTablesColumn(_("Device Users"), sort_type=DTSortType.NUMERIC),
        DataTablesColumn(_("Message"), sort_type=DTSortType.NUMERIC),
        DataTablesColumn(_("Version"), sort_type=DTSortType.NUMERIC)

    )

    context = get_hqadmin_base_context(request)
    context["headers"] = headers
    context["aoColumns"] = headers.render_aoColumns
    context["rows"] = rows

    return render(request, template, context)


@require_superuser
def mass_email(request):
    if not request.couch_user.is_staff:
        raise Http404()

    if request.method == "POST":
        form = EmailForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data['email_subject']
            body = form.cleaned_data['email_body']
            real_email = form.cleaned_data['real_email']

            if real_email:
                recipients = WebUser.view(
                    'users/mailing_list_emails',
                    reduce=False,
                    include_docs=True,
                ).all()
            else:
                recipients = [request.couch_user]

            for recipient in recipients:
                params = {
                    'email_body': body,
                    'user_id': recipient.get_id,
                    'unsub_url': get_url_base() +
                                 reverse('unsubscribe', args=[recipient.get_id])
                }
                text_content = render_to_string("hqadmin/email/mass_email_base.txt", params)
                html_content = render_to_string("hqadmin/email/mass_email_base.html", params)

                send_HTML_email(subject, recipient.email, html_content, text_content,
                                email_from=settings.DEFAULT_FROM_EMAIL)

            messages.success(request, 'Your email(s) were sent successfully.')

    else:
        form = EmailForm()

    context = get_hqadmin_base_context(request)
    context['hide_filters'] = True
    context['form'] = form
    return render(request, "hqadmin/mass_email.html", context)


@require_superuser
@get_file("file")
def update_domains(request):
    if request.method == "POST":
        try:
            workbook = WorkbookJSONReader(request.file)
            domains = workbook.get_worksheet(title='domains')
            success_count = 0
            fail_count = 0
            for row in domains:
                try:
                    name = row["name"]
                    domain = Domain.get_by_name(name)
                    if domain:
                        for k, v in row.items():
                            setattr(domain, k, v)
                        domain.save()
                        success_count += 1
                    else:
                        messages.warning(request, "No domain with name %s found" % name)
                        fail_count += 1
                except Exception, e:
                    messages.warning(request, "Update for %s failed: %s" % (row.get("name", '<No Name>'), e))
                    fail_count += 1
            if success_count:
                messages.success(request, "%s domains successfully updated" % success_count)
            if fail_count:
                messages.error(request, "%s domains had errors. details above." % fail_count)
            
        except Exception, e:
            messages.error(request, "Something went wrong! Update failed. Here's your error: %s" % e)
            
    # one wonders if this will eventually have to paginate
    domains = Domain.get_all()
    from corehq.apps.domain.calculations import _all_domain_stats
    all_stats = _all_domain_stats()
    for dom in domains:
        dom.web_users = int(all_stats["web_users"][dom.name])
        dom.commcare_users = int(all_stats["commcare_users"][dom.name])
        dom.cases = int(all_stats["cases"][dom.name])
        dom.forms = int(all_stats["forms"][dom.name])
        if dom.forms:
            try:
                dom.first_submission = string_to_datetime(XFormInstance.get_db().view\
                    ("couchforms/all_submissions_by_domain",
                     reduce=False, limit=1, 
                     startkey=[dom.name, "by_date"],
                     endkey=[dom.name, "by_date", {}]).all()[0]["key"][2]).strftime("%Y-%m-%d")
            except Exception:
                dom.first_submission = ""
            
            try:
                dom.last_submission = string_to_datetime(XFormInstance.get_db().view\
                    ("couchforms/all_submissions_by_domain",
                     reduce=False, limit=1, descending=True,
                     startkey=[dom.name, "by_date", {}],
                     endkey=[dom.name, "by_date"]).all()[0]["key"][2]).strftime("%Y-%m-%d")
            except Exception:
                dom.last_submission = ""
        else:
            dom.first_submission = ""
            dom.last_submission = ""
            
        
    context = get_hqadmin_base_context(request)
    context.update({"domains": domains})
    
    headers = DataTablesHeader(
        DataTablesColumn("Domain"),
        DataTablesColumn("City"),
        DataTablesColumn("Countries"),
        DataTablesColumn("Region"),
        DataTablesColumn("Project Type"),
        DataTablesColumn("Customer Type"),
        DataTablesColumn("Is Test"),
        DataTablesColumn("# Web Users", sort_type=DTSortType.NUMERIC),
        DataTablesColumn("# Mobile Workers", sort_type=DTSortType.NUMERIC),
        DataTablesColumn("# Cases", sort_type=DTSortType.NUMERIC),
        DataTablesColumn("# Submitted Forms", sort_type=DTSortType.NUMERIC),
        DataTablesColumn("First Submission"),
        DataTablesColumn("Most Recent Submission"),
        DataTablesColumn("Edit")
    )
    context["headers"] = headers
    context["aoColumns"] = headers.render_aoColumns
    return render(request, "hqadmin/domain_update_properties.html", context)

@require_superuser
def domain_list_download(request):
    domains = Domain.get_all()
    properties = ("name", "city", "countries", "region", "project_type",
                  "customer_type", "is_test?")
    
    def _row(domain):
        def _prop(domain, prop):
            if prop.endswith("?"):
                return yesno(getattr(domain, prop[:-1], ""))
            return getattr(domain, prop, "")
        return (_prop(domain, prop) for prop in properties)
    
    temp = StringIO()
    headers = (("domains", properties),)   
    data = (("domains", (_row(domain) for domain in domains)),)
    export_raw(headers, data, temp)
    return export_response(temp, Format.XLS_2007, "domains")


@require_superuser_or_developer
def download_recent_changes(request):
    count = int(request.GET.get('changes', 10000))
    resp = HttpResponse(content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename="recent_changes.csv"'
    download_changes(get_db(), count, resp)
    return resp


@require_superuser_or_developer
def system_ajax(request):
    """
    Utility ajax functions for polling couch and celerymon
    """
    type = request.GET.get('api', None)
    task_limit = getattr(settings, 'CELERYMON_TASK_LIMIT', 12)
    celery_monitoring = getattr(settings, 'CELERY_FLOWER_URL', None)
    db = XFormInstance.get_db()
    if type == "_active_tasks":
        tasks = [] if is_bigcouch() else filter(lambda x: x['type'] == "indexer", db.server.active_tasks())
        #for reference structure is:
        #        tasks = [{'type': 'indexer', 'pid': 'foo', 'database': 'mock',
        #            'design_document': 'mockymock', 'progress': 0,
        #            'started_on': 1349906040.723517, 'updated_on': 1349905800.679458,
        #            'total_changes': 1023},
        #            {'type': 'indexer', 'pid': 'foo', 'database': 'mock',
        #            'design_document': 'mockymock', 'progress': 70,
        #            'started_on': 1349906040.723517, 'updated_on': 1349905800.679458,
        #            'total_changes': 1023}]
        return json_response(tasks)
    elif type == "_stats":
        return json_response({})
    elif type == "_logs":
        pass
    elif type == 'pillowtop':
        return json_response(get_all_pillows_json())
    elif type == 'stale_pillows':
        es_index_status = [
            check_case_es_index(interval=3),
            check_xform_es_index(interval=3),
            check_reportcase_es_index(interval=3),
            check_reportxform_es_index(interval=3)
        ]
        return json_response(es_index_status)

    if celery_monitoring:
        cresource = Resource(celery_monitoring, timeout=3)
        if type == "flower_poll":
            ret = []
            try:
                t = cresource.get("api/tasks", params_dict={'limit': task_limit}).body_string()
                all_tasks = json.loads(t)
            except Exception, ex:
                all_tasks = {}
                logging.error("Error with getting from celery_flower: %s" % ex)

            for task_id, traw in all_tasks.items():
                # it's an array of arrays - looping through [<id>, {task_info_dict}]
                if 'name' in traw and traw['name']:
                    traw['name'] = '.'.join(traw['name'].split('.')[-2:])
                else:
                    traw['name'] = None
                ret.append(traw)
            ret = sorted(ret, key=lambda x: x['succeeded'], reverse=True)
            return HttpResponse(json.dumps(ret), mimetype = 'application/json')
    return HttpResponse('{}', mimetype='application/json')


@require_superuser_or_developer
def system_info(request):
    environment = settings.SERVER_ENVIRONMENT

    context = get_hqadmin_base_context(request)
    context['couch_update'] = request.GET.get('couch_update', 5000)
    context['celery_update'] = request.GET.get('celery_update', 10000)
    context['db_update'] = request.GET.get('db_update', 30000)
    context['celery_flower_url'] = getattr(settings, 'CELERY_FLOWER_URL', None)

    # recent changes
    recent_changes = int(request.GET.get('changes', 50))
    context['recent_changes'] = get_recent_changes(get_db(), recent_changes)
    context['rabbitmq_url'] = get_rabbitmq_management_url()
    context['hide_filters'] = True
    context['current_system'] = socket.gethostname()
    context['deploy_history'] = HqDeploy.get_latest(environment, limit=5)

    context.update(check_redis())
    context.update(check_rabbitmq())
    context.update(check_celery_health())
    context.update(check_memcached())
    context.update(check_es_cluster_health())

    return render(request, "hqadmin/system_info.html", context)


@cache_page(60 * 5)
@require_superuser_or_developer
def db_comparisons(request):
    comparison_config = [
        {
            'description': 'Users (base_doc is "CouchUser")',
            'couch_db': CommCareUser.get_db(),
            'view_name': 'users/by_username',
            'es_query': UserES().remove_default_filter('active').size(0),
            'sql_rows': User.objects.count(),
        },
        {
            'description': 'Domains (doc_type is "Domain")',
            'couch_db': Domain.get_db(),
            'view_name': 'domain/by_status',
            'es_query': DomainES().size(0),
            'sql_rows': None,
        },
        {
            'description': 'Forms (doc_type is "XFormInstance")',
            'couch_db': XFormInstance.get_db(),
            'view_name': 'couchforms/by_xmlns',
            'es_query': FormES().remove_default_filter('has_xmlns')
                .remove_default_filter('has_user')
                .size(0),
            'sql_rows': FormData.objects.count(),
        },
        {
            'description': 'Cases (doc_type is "CommCareCase")',
            'couch_db': CommCareCase.get_db(),
            'view_name': 'case/by_owner',
            'es_query': CaseES().size(0),
            'sql_rows': None,
        }
    ]

    comparisons = []
    for comp in comparison_config:
        comparisons.append({
            'description': comp['description'],
            'couch_docs': comp['couch_db'].view(
                    comp['view_name'],
                    reduce=True,
                ).one()['value'],
            'es_docs': comp['es_query'].run().total,
            'sql_rows': comp['sql_rows'] if comp['sql_rows'] else 'n/a',
        })
    return json_response(comparisons)

@require_POST
@require_superuser_or_developer
def reset_pillow_checkpoint(request):
    pillow = get_pillow_by_name(request.POST["pillow_name"])
    if pillow:
        pillow.reset_checkpoint()

    return redirect("system_info")

@require_superuser
def noneulized_users(request, template="hqadmin/noneulized_users.html"):
    context = get_hqadmin_base_context(request)

    days = request.GET.get("days", None)
    days = int(days) if days else 60
    days_ago = datetime.now() - timedelta(days=days)

    users = WebUser.view("eula_report/noneulized_users",
        reduce=False,
        include_docs=True,
        startkey =["WebUser", days_ago.strftime("%Y-%m-%dT%H:%M:%SZ")],
        endkey =["WebUser", {}]
    ).all()

    context.update({"users": filter(lambda user: not user.is_dimagi, users), "days": days})

    headers = DataTablesHeader(
        DataTablesColumn("Username"),
        DataTablesColumn("Date of Last Login"),
        DataTablesColumn("couch_id"),
    )
    context['layout_flush_content'] = True
    context["headers"] = headers
    context["aoColumns"] = headers.render_aoColumns

    return render(request, template, context)


@require_superuser
@cache_page(60*5)
def all_commcare_settings(request):
    apps = ApplicationBase.view('app_manager/applications_brief',
                                include_docs=True)
    filters = set()
    for param in request.GET:
        s_type, name = param.split('.')
        value = request.GET.get(param)
        filters.add((s_type, name, value))

    def app_filter(settings):
        for s_type, name, value in filters:
            if settings[s_type].get(name) != value:
                return False
        return True

    settings_list = [s for s in (get_settings_values(app) for app in apps)
                     if app_filter(s)]
    return json_response(settings_list)


def find_broken_suite_files(request):
    from corehq.apps.app_manager.management.commands.find_broken_suite_files import find_broken_suite_files
    try:
        start = request.GET['start']
        end = request.GET['end']
    except KeyError:
        return HttpResponseBadRequest()
    # streaming doesn't seem to work; it stops part-way through
    return HttpResponse(''.join(find_broken_suite_files(start, end)),
                        mimetype='text/plain')


@require_superuser
@require_GET
def admin_restore(request):
    full_username = request.GET.get('as', '')
    if not full_username or '@' not in full_username:
        return HttpResponseBadRequest('Please specify a user using ?as=user@domain')

    username, domain = full_username.split('@')
    if not domain.endswith(settings.HQ_ACCOUNT_ROOT):
        full_username = format_username(username, domain)

    user = CommCareUser.get_by_username(full_username)
    if not user:
        return HttpResponseNotFound('User %s not found.' % full_username)

    overwrite_cache = request.GET.get('ignore_cache') == 'true'
    return get_restore_response(user.domain, user, overwrite_cache=overwrite_cache, **get_restore_params(request))

@require_superuser
def management_commands(request, template="hqadmin/management_commands.html"):
    commands = [(_('Remove Duplicate Domains'), 'remove_duplicate_domains')]
    context = get_hqadmin_base_context(request)
    context["hide_filters"] = True
    context["commands"] = commands
    return render(request, template, context)


@require_POST
@require_superuser
def run_command(request):
    cmd = request.POST.get('command')
    if cmd not in ['remove_duplicate_domains']: # only expose this one command for now
        return json_response({"success": False, "output": "Command not available"})

    output_buf = StringIO()
    management.call_command(cmd, stdout=output_buf)
    output = output_buf.getvalue()
    output_buf.close()

    return json_response({"success": True, "output": output})


class FlagBrokenBuilds(FormView):
    template_name = "hqadmin/flag_broken_builds.html"
    form_class = BrokenBuildsForm

    @method_decorator(require_superuser)
    def dispatch(self, *args, **kwargs):
        return super(FlagBrokenBuilds, self).dispatch(*args, **kwargs)

    def form_valid(self, form):
        db = ApplicationBase.get_db()
        build_jsons = db.all_docs(keys=form.build_ids, include_docs=True)
        docs = []
        for doc in [build_json['doc'] for build_json in build_jsons.all()]:
            if doc.get('doc_type') in ['Application', 'RemoteApp']:
                doc['build_broken'] = True
                docs.append(doc)
        db.bulk_save(docs)
        return HttpResponse("posted!")


@require_superuser
@datespan_in_request(from_param="startdate", to_param="enddate", default_days=365)
def stats_data(request):
    histo_type = request.GET.get('histogram_type')
    interval = request.GET.get("interval", "week")
    datefield = request.GET.get("datefield")
    get_request_params_json = request.GET.get("get_request_params", None)
    get_request_params = (
        json.loads(HTMLParser.HTMLParser().unescape(get_request_params_json))
        if get_request_params_json is not None else {}
    )

    stats_kwargs = {
        k: get_request_params[k]
        for k in get_request_params if k != "domain_params_es"
    }
    if datefield is not None:
        stats_kwargs['datefield'] = datefield

    domain_params_es = get_request_params.get("domain_params_es", {})

    if not request.GET.get("enddate"):  # datespan should include up to the current day when unspecified
        request.datespan.enddate += timedelta(days=1)

    domain_params, __ = parse_args_for_es(request, prefix='es_')
    domain_params.update(domain_params_es)

    domains = get_project_spaces(facets=domain_params)

    return json_response(get_stats_data(
        histo_type,
        domains,
        request.datespan,
        interval,
        **stats_kwargs
    ))


@require_superuser
@datespan_in_request(from_param="startdate", to_param="enddate", default_days=365)
def admin_reports_stats_data(request):
    return stats_data(request)


@require_superuser
def loadtest(request):
    # The multimech results api is kinda all over the place.
    # the docs are here: http://testutils.org/multi-mechanize/datastore.html

    scripts = ['submit_form.py', 'ota_restore.py']

    tests = []
    # datetime info seems to be buried in GlobalConfig.results[0].run_id,
    # which makes ORM-level sorting problematic
    for gc in Session.query(GlobalConfig).all()[::-1]:
        gc.scripts = dict((uc.script, uc) for uc in gc.user_group_configs)
        if gc.results:
            for script, uc in gc.scripts.items():
                uc.results = filter(
                    lambda res: res.user_group_name == uc.user_group,
                    gc.results
                )
            test = {
                'datetime': gc.results[0].run_id,
                'run_time': gc.run_time,
                'results': gc.results,
            }
            for script in scripts:
                test[script.split('.')[0]] = gc.scripts.get(script)
            tests.append(test)

    context = get_hqadmin_base_context(request)
    context.update({
        "tests": tests,
        "hide_filters": True,
    })

    date_axis = Axis(label="Date", dateFormat="%m/%d/%Y")
    tests_axis = Axis(label="Number of Tests in 30s")
    chart = LineChart("HQ Load Test Performance", date_axis, tests_axis)
    submit_data = []
    ota_data = []
    total_data = []
    max_val = 0
    max_date = None
    min_date = None
    for test in tests:
        date = test['datetime']
        total = len(test['results'])
        max_val = total if total > max_val else max_val
        max_date = date if not max_date or date > max_date else max_date
        min_date = date if not min_date or date < min_date else min_date
        submit_data.append({'x': date, 'y': len(test['submit_form'].results)})
        ota_data.append({'x': date, 'y': len(test['ota_restore'].results)})
        total_data.append({'x': date, 'y': total})

    deployments = [row['key'][1] for row in HqDeploy.get_list(settings.SERVER_ENVIRONMENT, min_date, max_date)]
    deploy_data = [{'x': min_date, 'y': 0}]
    for date in deployments:
        deploy_data.extend([{'x': date, 'y': 0}, {'x': date, 'y': max_val}, {'x': date, 'y': 0}])
    deploy_data.append({'x': max_date, 'y': 0})

    chart.add_dataset("Deployments", deploy_data)
    chart.add_dataset("Form Submission Count", submit_data)
    chart.add_dataset("OTA Restore Count", ota_data)
    chart.add_dataset("Total Count", total_data)

    context['charts'] = [chart]

    template = "hqadmin/loadtest.html"
    return render(request, template, context)

@require_superuser
def doc_in_es(request):
    doc_id = request.GET.get("id")
    if not doc_id:
        return render(request, "hqadmin/doc_in_es.html", {})
    try:
        couch_doc = get_db().get(doc_id)
    except ResourceNotFound:
        couch_doc = {}
    query = {"filter":
                {"ids": {
                    "values": [doc_id]}}}

    def to_json(doc):
        return json.dumps(doc, indent=4, sort_keys=True) if doc else "NOT FOUND!"

    found_indices = {}
    doc_type = couch_doc.get('doc_type')
    es_doc_type = None
    for index, url in ES_URLS.items():
        res = run_query(url, query)
        if res['hits']['total'] == 1:
            es_doc = res['hits']['hits'][0]['_source']
            found_indices[index] = to_json(es_doc)
            es_doc_type = es_doc_type or es_doc.get('doc_type')

    doc_type = doc_type or es_doc_type or 'Unknown'

    context = {
        "doc_id": doc_id,
        "status": "found" if found_indices else "NOT FOUND!",
        "doc_type": doc_type,
        "couch_doc": to_json(couch_doc),
        "found_indices": found_indices,
    }
    return render(request, "hqadmin/doc_in_es.html", context)


@require_superuser
def callcenter_test(request):
    user_id = request.GET.get("user_id")
    date_param = request.GET.get("date")
    enable_caching = request.GET.get('cache')
    doc_id = request.GET.get('doc_id')

    if not user_id and not doc_id:
        return render(request, "hqadmin/callcenter_test.html", {"enable_caching": enable_caching})

    error = None
    user = None
    user_case = None
    domain = None
    if user_id:
        try:
            user = CommCareUser.get(user_id)
            domain = user.project
        except ResourceNotFound:
            error = "User Not Found"
    elif doc_id:
        try:
            doc = CommCareUser.get_db().get(doc_id)
            doc_type = doc.get('doc_type', None)
            if doc_type == 'CommCareUser':
                user_case = get_case_by_domain_hq_user_id(doc['domain'], doc['_id'], include_docs=True)
            elif doc_type == 'CommCareCase':
                if doc.get('hq_user_id'):
                    user_case = CommCareCase.wrap(doc)
                else:
                    error = 'Case ID does does not refer to a Call Center Case'
        except ResourceNotFound:
            error = "User Not Found"

    if user_case:
        domain = Domain.get_by_name(user_case['domain'])

    try:
        query_date = dateutil.parser.parse(date_param)
    except ValueError:
        error = "Unable to parse date, using today"
        query_date = date.today()

    def view_data(case_id, indicators):
        new_dict = SortedDict()
        key_list = sorted(indicators.keys())
        for key in key_list:
            new_dict[key] = indicators[key]
        return {
            'indicators': new_dict,
            'case': CommCareCase.get(case_id),
        }

    if user or user_case:
        custom_cache = None if enable_caching else cache.get_cache('django.core.cache.backends.dummy.DummyCache')
        cci = CallCenterIndicators(
            domain,
            user,
            custom_cache=custom_cache,
            override_date=query_date,
            override_cases=[user_case] if user_case else None
        )
        data = {case_id: view_data(case_id, values) for case_id, values in cci.get_data().items()}
    else:
        data = {}

    context = {
        "error": error,
        "mobile_user": user,
        "date": query_date.strftime("%Y-%m-%d"),
        "enable_caching": enable_caching,
        "data": data,
        "doc_id": doc_id
    }
    return render(request, "hqadmin/callcenter_test.html", context)


class PrimeRestoreCache(FormView):
    template_name = "hqadmin/prime_restore_cache.html"
    form_class = PrimeRestoreCacheForm

    @method_decorator(require_superuser)
    def dispatch(self, *args, **kwargs):
        return super(PrimeRestoreCache, self).dispatch(*args, **kwargs)

    def form_valid(self, form):
        domain = form.cleaned_data['domain']
        if form.cleaned_data['all_users']:
            user_ids = CommCareUser.ids_by_domain(domain)
        else:
            user_ids = form.user_ids

        download = DownloadBase()
        res = prime_restore.delay(
            domain,
            user_ids,
            version=form.cleaned_data['version'],
            cache_timeout_hours=form.cleaned_data['cache_timeout'],
            overwrite_cache=form.cleaned_data['overwrite_cache'],
            check_cache_only=form.cleaned_data['check_cache_only']
        )
        download.set_task(res)

        return redirect('hq_soil_download', domain, download.download_id)
