import datetime as DT
import dateutil.parser
from dimagi.utils.web import render_to_response
from dimagi.utils.parsing import string_to_datetime
from dimagi.utils.couch.database import get_db
from collections import defaultdict
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from .googlecharts import get_punchcard_url
from .calc import punchcard
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.reports.templatetags.report_tags import render_user_inline
from dimagi.utils.couch.pagination import CouchPaginator

from couchexport.export import export_excel
from StringIO import StringIO

iso_format = '%Y-%m-%dT%H:%M:%SZ'

#def report_list(request, domain):
#    template = "reports/report_list.html"
#    return render_to_response(request, template, {'domain': domain})

@login_and_domain_required
def default(request, domain):
    return HttpResponseRedirect(reverse("individual_summary_report", args=[domain]))

@login_and_domain_required
def export_data(req, domain):
    """
    Download all data for a couchdbkit model
    """
    export_tag = req.GET.get("export_tag", "")
    if not export_tag:
        raise Exception("You must specify a model to download!")
    tmp = StringIO()
    if export_excel([domain, export_tag], tmp):
        response = HttpResponse(mimetype='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename=%s.xls' % export_tag
        response.write(tmp.getvalue())
        tmp.close()
        return response
    else:
        return HttpResponse("Sorry, there was no data found for the tag '%s'." % export_tag)


@login_and_domain_required
def submit_history(request, domain, template="reports/partials/couch_report_partial.html"):
    individual = request.GET.get('individual', '')
    rows = []

    if individual:
        headings = ["Submit Time", "Form"]
    else:
        headings = ["Username", "Submit Time", "XMLNS"]
    return render_to_response(request, template, {
        'headings': headings,
        'rows': rows,
        'ajax_source': reverse('paging_submit_history', args=[domain, individual]),
    })
def paging_submit_history(request, domain, individual):
    print "individual %s" % individual

    def xmlns_to_name(xmlns):
        try:
            form = get_db().view('reports/forms_by_xmlns', key=[domain, xmlns], group=True).one()['value']
            lang = form['app']['langs'][0]
        except:
            form = None

        if form:
            name = "%s > %s > %s" % (
                form['app']['name'],
                form['module']['name'][lang],
                form['form']['name'][lang]
            )
        else:
            name = xmlns
        return name
    def format_time(time):
        "time is an ISO timestamp"
        return time.replace('T', ' ').replace('Z', '')

    if individual:
        def view_to_table(row):
            time = row['value'].get('time')
            xmlns = row['value'].get('xmlns')

            #time = DT.datetime.strptime(time, iso_format)
            time = format_time(time)
            xmlns = xmlns_to_name(xmlns)
            return [time, xmlns]
        paginator = CouchPaginator('reports/submit_history', view_to_table, search=False, view_args=dict(
            endkey=[domain, individual],
            startkey=[domain, individual, {}],
            #descending=True,
        ))
    else:
        def view_to_table(row):
            time = row['value'].get('time')
            xmlns = row['value'].get('xmlns')
            username = row['value'].get('username')

            #time = DT.datetime.strptime(time, iso_format)
            time = format_time(time)
            xmlns = xmlns_to_name(xmlns)            
            return [username, time, xmlns]
        paginator = CouchPaginator('reports/all_submissions', view_to_table, search=False, view_args=dict(
            endkey=[domain],
            startkey=[domain, {}],
            #descending=True,
        ))
    return paginator.get_ajax_response(request)

@login_and_domain_required
def submit_time_punchcard(request, domain):
    individual = request.GET.get("individual", '')
    data = punchcard.get_data(domain, individual)
    url = get_punchcard_url(data)
    #user_data = punchcard.get_users(domain)
#    if individual:
#        selected_user = [user for user, _ in user_data if user["_id"] == user_id][0]
#        name = "Punchcard Report for %s at %s" % (render_user_inline(selected_user))
    return render_to_response(request, "reports/punchcard.html", {
        "chart_url": url,
        #"user_data": user_data,
        #"clinic_id": clinic_id,
        #"user_id": user_id
    })

@login_and_domain_required
def user_summary(request, domain, template="reports/user_summary.html"):
    report_name = "User Summary Report (number of forms filled in by person)"

    return render_to_response(request, template, {
        "domain": domain,
        "show_dates": False,
        "report": {
            "name": report_name
        },
        "ajax_source": reverse('paging_user_summary', args=[domain]), 
    })

@login_and_domain_required
def paging_user_summary(request, domain, template="reports/user_summary.html"):

    def view_to_table(row):
        row['last_submission_date'] = dateutil.parser.parse(row['last_submission_date'])
        return row
    paginator = CouchPaginator(
        "reports/user_summary",
        view_to_table,
        search=False,
        view_args=dict(
            group=True,
            startkey=[domain],
            endkey=[domain, {}],
        )
    )
    return paginator.get_ajax_response(request)

@login_and_domain_required
def individual_summary(request, domain):
    individual = request.GET.get('individual', '')
    if individual:
        pass

    usernames = get_db().view('reports/all_users', startkey=[domain], endkey=[domain, {}], group=True)
    usernames = [result['key'][1] for result in usernames]
    return render_to_response(request, "reports/individual_summary.html", {
        "domain": domain,
        "show_users": True,
        "report": {
            "name": "Individual Summary",
            "header": [],
            "rows": [],
        },
        "usernames": usernames,
        "individual": individual,
    })

@login_and_domain_required
def daily_submissions(request, domain, view_name, title):
    start_date = request.GET.get('startdate')
    end_date = request.GET.get('enddate')
    if end_date:
        end_date = DT.date(*map(int, end_date.split('-')))
    else:
        end_date = DT.datetime.utcnow().date()

    if start_date:
        start_date = DT.date(*map(int, start_date.split('-')))
    else:
        start_date = (end_date- DT.timedelta(days=6))
    results = get_db().view(
        view_name,
        group=True,
        startkey=[domain, start_date.isoformat()],
        endkey=[domain, end_date.isoformat()]
    ).all()
    all_users_results = get_db().view("reports/all_users", startkey=[domain], endkey=[domain, {}], group=True).all()
    usernames = [result['key'][1] for result in all_users_results]

    dates = [start_date]
    while dates[-1] < end_date:
        dates.append(dates[-1] + DT.timedelta(days=1))
    date_map = dict([(date.isoformat(), i+1) for (i,date) in enumerate(dates)])
    username_map = dict([(username, i) for (i, username) in enumerate(usernames)])
    rows = [[0]*(1+len(date_map)) for _ in usernames]
    for result in results:
        _, date, username = result['key']
        val = result['value']
        rows[username_map[username]][date_map[date]] = val
    for i,username in enumerate(usernames):
        rows[i][0] = username

    headers = ["Username"] + dates
    print "end date: %s" % end_date
    return render_to_response(request, "reports/daily_submissions.html", {
        "domain": domain,
        "show_dates": True,
        "start_date": start_date,
        "end_date": end_date,
        "report": {
            "name": title,
            "headers": headers,
            "rows": rows,
        }
    })

@login_and_domain_required
def excel_export_data(request, domain, template="reports/excel_export_data.html"):
    forms = get_db().view('reports/forms_by_xmlns', startkey=[domain], endkey=[domain, {}], group=True)
    forms = [x['value'] for x in forms]

    forms = sorted(forms, key=lambda form: \
        (0, form['app']['name'], form['module']['id'], form['form']['id']) \
        if 'app' in form else \
        (1, form['xmlns'])
    )

    apps = []
    unknown_forms = []

    # organize forms into apps, modules, forms:
    #        apps = [
    #            {
    #                "name": "App",
    #                "modules": [
    #                    {
    #                        "name": "Module 1",
    #                        "id": 1,
    #                        "forms": [
    #                            {...}
    #                        ]
    #                    }
    #                ]
    #
    #            }
    #        ]

    for f in forms:
        if 'app' in f:
            if apps and f['app']['name'] == apps[-1]['name']:
                if f['module']['id'] == apps[-1]['modules'][-1]['id']:
                    apps[-1]['modules'][-1]['forms'].append(f)
                else:
                    module = f['module'].copy()
                    module.update(forms=[f])
                    apps[-1]['modules'].append(module)
            else:
                app = f['app'].copy()
                module = f['module'].copy()
                module.update(forms=[f])
                app.update(modules=[module])
                apps.append(app)

        else:
            unknown_forms.append(f)


    return render_to_response(request, template, {
        "domain": domain,
        "forms": forms,
        "forms_by_app": apps,
        "unknown_forms": unknown_forms,
        "report": {
            "name": "Export Data to Excel"
        }
    })

    