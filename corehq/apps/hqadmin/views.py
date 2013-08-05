from datetime import timedelta, datetime
import json
from copy import deepcopy
import logging
from collections import defaultdict
from StringIO import StringIO
import socket

from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST, require_GET
from pytz import timezone
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseBadRequest, HttpResponseNotFound
from django.core.urlresolvers import reverse
from django.shortcuts import render
from django.views.decorators.cache import cache_page
from django.template.defaultfilters import yesno
from django.contrib import messages
from django.conf import settings
from restkit import Resource
from django.core import cache
from django.utils import html
from django.utils.translation import ugettext as _
from django.core import management

from corehq.apps.app_manager.models import ApplicationBase
from corehq.apps.app_manager.util import get_settings_values
from corehq.apps.hqadmin.models import HqDeploy
from corehq.apps.hqadmin.forms import EmailForm
from corehq.apps.builds.models import CommCareBuildConfig, BuildSpec
from corehq.apps.domain.models import Domain
from corehq.apps.hqadmin.escheck import check_cluster_health, check_case_index, check_xform_index
from corehq.apps.ota.views import get_restore_response, get_restore_params
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader, DTSortType
from corehq.apps.reports.util import make_form_couch_key
from corehq.apps.sms.models import SMSLog
from corehq.apps.users.models import  CommCareUser, WebUser
from corehq.apps.users.util import format_username
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db, is_bigcouch
from corehq.apps.domain.decorators import  require_superuser
from dimagi.utils.decorators.datespan import datespan_in_request
from dimagi.utils.parsing import json_format_datetime, string_to_datetime
from dimagi.utils.web import json_response, get_url_base
from couchexport.export import export_raw, export_from_tables
from couchexport.shortcuts import export_response
from couchexport.models import Format
from dimagi.utils.excel import WorkbookJSONReader
from dimagi.utils.decorators.view import get_file
from dimagi.utils.timezones import utils as tz_utils
from django.utils.translation import ugettext as _
from dimagi.utils.django.email import send_HTML_email
from django.template.loader import render_to_string
from corehq.apps.users.models import CouchUser
from django.http import Http404


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

        key = [domain.name, "all_errors_only"]
        data = get_db().view("phonelog/devicelog_data",
            reduce=True,
            startkey=key+[datespan.startdate_param_utc],
            endkey=key+[datespan.enddate_param_utc],
            stale=settings.COUCH_STALE_QUERY,
        ).first()
        num_errors = 0
        num_warnings = 0
        if data:
            data = data.get('value', {})
            num_errors = data.get('errors', 0)
            num_warnings = data.get('warnings', 0)

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
    domains = Domain.get_all()

    rows = []
    for domain in domains:
        data = get_db().view("phonelog/devicelog_data",
            reduce=False,
            startkey=[domain.name, "tag", "user-report"],
            endkey=[domain.name, "tag", "user-report", {}],
            stale=settings.COUCH_STALE_QUERY,
        ).all()
        for report in data:
            val = report.get('value')
            version = val.get('version', 'unknown')
            formatted_date = tz_utils.string_to_prertty_time(val['@date'], timezone(domain.default_timezone), fmt="%b %d, %Y %H:%M:%S")
            rows.append(dict(domain=domain.name,
                             time=formatted_date,
                             user=val['user'],
                             device_users=val['device_users'],
                             message=val['msg'],
                             version=version.split(' ')[0],
                             detailed_version=html.escape(version),
                             report_id=report['id']))

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
                    ("receiverwrapper/all_submissions_by_domain", 
                     reduce=False, limit=1, 
                     startkey=[dom.name, "by_date"],
                     endkey=[dom.name, "by_date", {}]).all()[0]["key"][2]).strftime("%Y-%m-%d")
            except Exception:
                dom.first_submission = ""
            
            try:
                dom.last_submission = string_to_datetime(XFormInstance.get_db().view\
                    ("receiverwrapper/all_submissions_by_domain", 
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
        DataTablesColumn("Country"),
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
    properties = ("name", "city", "country", "region", "project_type", 
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

@require_superuser
def system_ajax(request):
    """
    Utility ajax functions for polling couch and celerymon
    """
    type = request.GET.get('api', None)
    task_limit = getattr(settings, 'CELERYMON_TASK_LIMIT', 12)
    celery_monitoring = getattr(settings, 'CELERY_FLOWER_URL', None)
    db = XFormInstance.get_db()
    ret = {}
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
        return HttpResponse(json.dumps(tasks), mimetype='application/json')
    elif type == "_stats":
        return HttpResponse(json.dumps({}), mimetype = 'application/json')
    elif type == "_logs":
        pass

    if celery_monitoring:
        cresource = Resource(celery_monitoring, timeout=3)
        if type == "flower_poll":
            ret = []
            try:
                t = cresource.get("api/tasks", params_dict={'limit': task_limit}).body_string()
                all_tasks = json.loads(t)
            except Exception, ex:
                all_tasks = []
                t = {}
                logging.error("Error with getting from celery_flower: %s" % ex)

            for task_id, traw in all_tasks.items():
                # it's an array of arrays - looping through [<id>, {task_info_dict}]
                traw['name'] = '.'.join(traw['name'].split('.')[-2:])
                ret.append(traw)
            ret = sorted(ret, key=lambda x: x['succeeded'], reverse=True)
            return HttpResponse(json.dumps(ret), mimetype = 'application/json')
    return HttpResponse('{}', mimetype='application/json')


@require_superuser
def system_info(request):

    def human_bytes(bytes):
        #source: https://github.com/bartTC/django-memcache-status
        bytes = float(bytes)
        if bytes >= 1073741824:
            gigabytes = bytes / 1073741824
            size = '%.2fGB' % gigabytes
        elif bytes >= 1048576:
            megabytes = bytes / 1048576
            size = '%.2fMB' % megabytes
        elif bytes >= 1024:
            kilobytes = bytes / 1024
            size = '%.2fKB' % kilobytes
        else:
            size = '%.2fB' % bytes
        return size

    context = get_hqadmin_base_context(request)

    context['couch_update'] = request.GET.get('couch_update', 5000)
    context['celery_update'] = request.GET.get('celery_update', 10000)
    context['celery_flower_url'] = settings.CELERY_FLOWER_URL

    context['rabbitmq_url'] = get_rabbitmq_management_url()

    context['hide_filters'] = True
    context['current_system'] = socket.gethostname()

    environment = settings.SERVER_ENVIRONMENT
    context['last_deploy'] = HqDeploy.get_latest(environment)

    context['snapshot'] = context['last_deploy'].code_snapshot if context['last_deploy'] else {}

    #redis status
    redis_status = ""
    redis_results = ""
    if 'redis' in settings.CACHES:
        rc = cache.get_cache('redis')
        try:
            import redis
            redis_api = redis.StrictRedis.from_url('redis://%s' % rc._server)
            info_dict = redis_api.info()
            redis_status = "Online"
            redis_results = "Used Memory: %s" % info_dict['used_memory_human']
        except Exception, ex:
            redis_status = "Offline"
            redis_results = "Redis connection error: %s" % ex
    else:
        redis_status = "Not Configured"
        redis_results = "Redis is not configured on this system!"

    context['redis_status'] = redis_status
    context['redis_results'] = redis_results

    #rabbitmq status
    mq_status = "Unknown"
    if settings.BROKER_URL.startswith('amqp'):
        amqp_parts = settings.BROKER_URL.replace('amqp://','').split('/')
        mq_management_url = amqp_parts[0].replace('5672', '15672')
        vhost = amqp_parts[1]
        try:
            mq = Resource('http://%s' % mq_management_url, timeout=2)
            vhost_dict = json.loads(mq.get('api/vhosts', timeout=2).body_string())
            mq_status = "Offline"
            for d in vhost_dict:
                if d['name'] == vhost:
                    mq_status='RabbitMQ OK'
        except Exception, ex:
            mq_status = "RabbitMQ Error: %s" % ex
    else:
        mq_status = "RabbitMQ Not configured"
    context['rabbitmq_status'] = mq_status

    #celery task monitoring status
    celery_monitoring = getattr(settings, 'CELERY_FLOWER_URL', None)
    worker_status = ""
    if celery_monitoring:
        cresource = Resource(celery_monitoring, timeout=3)
        t = cresource.get("api/workers").body_string()
        all_workers = json.loads(t)
        worker_ok = '<span class="label label-success">OK</span>'
        worker_bad = '<span class="label label-important">Down</span>'

        tasks_ok = 'label-success'
        tasks_full = 'label-warning'


        worker_info = []
        for hostname, w in all_workers.items():
            status_html = mark_safe(worker_ok if w['status'] else worker_bad)
            tasks_class = tasks_full if w['running_tasks'] == w['concurrency'] else tasks_ok
            tasks_html = mark_safe('<span class="label %s">%d / %d</span> :: %d' % (tasks_class, w['running_tasks'], w['concurrency'], w['completed_tasks']))
            worker_info.append(' '.join([hostname, status_html, tasks_html]))
        worker_status = '<br>'.join(worker_info)
    context['worker_status'] = mark_safe(worker_status)


    #memcached_status
    mc = cache.get_cache('default')
    mc_status = "Unknown/Offline"
    mc_results = ""
    try:
        mc_stats = mc._cache.get_stats()
        if len(mc_stats) > 0:
            mc_status = "Online"
            stats_dict = mc_stats[0][1]
            bytes = stats_dict['bytes']
            max_bytes = stats_dict['limit_maxbytes']
            curr_items = stats_dict['curr_items']
            mc_results = "%s Items %s out of %s" % (curr_items, human_bytes(bytes),
                                                    human_bytes(max_bytes))

    except Exception, ex:
        mc_status = "Offline"
        mc_results = "%s" % ex
    context['memcached_status'] = mc_status
    context['memcached_results'] = mc_results


    #elasticsearch status
    #node status
    context.update(check_cluster_health())
    context.update(check_case_index())
    context.update(check_xform_index())

    return render(request, "hqadmin/system_info.html", context)

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
    return HttpResponse(find_broken_suite_files(start, end), mimetype='text/plain')

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
    return get_restore_response(user, **get_restore_params(request))

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
