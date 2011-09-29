from datetime import timedelta, datetime
import json
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import permission_required
from django.template.context import RequestContext
from corehq.apps.builds.models import CommCareBuildConfig, BuildSpec
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CouchUser, CommCareUser
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db
from collections import defaultdict
from corehq.apps.domain.decorators import login_and_domain_required
from dimagi.utils.parsing import json_format_datetime, string_to_datetime
from dimagi.utils.web import json_response, render_to_response

require_superuser = permission_required("is_superuser")

@require_superuser
def default(request):
    return HttpResponseRedirect(reverse("domain_list"))

@require_superuser
def domain_list(request):
    # one wonders if this will eventually have to paginate
    domains = Domain.objects.all().order_by("name")
    webuser_counts = defaultdict(lambda: 0)
    commcare_counts = defaultdict(lambda: 0)
    form_counts = defaultdict(lambda: 0)
    for row in get_db().view('users/by_domain', startkey=["active"], endkey=["active", {}], group_level=3).all():
        _, domain, doc_type = row['key']
        value = row['value']
        {
            'WebUser': webuser_counts,
            'CommCareUser': commcare_counts
        }[doc_type][domain] = value

    form_counts.update(dict([(row["key"][0], row["value"]) for row in get_db().view("reports/all_submissions", group=True,group_level=1).all()]))
    for dom in domains:
        dom.web_users = webuser_counts[dom.name]
        dom.commcare_users = commcare_counts[dom.name]
        dom.forms = form_counts[dom.name]
        dom.admins = [row["doc"]["email"] for row in get_db().view("users/admins_by_domain", key=dom.name, reduce=False, include_docs=True).all()]
    try:
        domain = request.user.selected_domain.name
    except AttributeError:
        domain = None
    return render_to_response(request, "hqadmin/domain_list.html",
                              {"domains": domains,
                               "domain": domain},
                              context_instance=RequestContext(request))


@require_superuser
def active_users(request):
    keys = []
    number_threshold = 15
    date_threshold_days_ago = 90
    date_threshold = json_format_datetime(datetime.utcnow() - timedelta(days=date_threshold_days_ago))
    for line in get_db().view("reports/submit_history", group_level=2):
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

    for domain, user_id in keys:
        if get_db().view("reports/submit_history", reduce=False, startkey=[domain, user_id, date_threshold], limit=1):
            if True or is_valid_user_id(user_id):
                final_count[domain] += 1

    return json_response({"break_down": final_count, "total": sum(final_count.values())})

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
    return render_to_response(request, template, {'tables': tables})

@require_superuser
def domain_activity_report(request, template="hqadmin/domain_activity_report.html"):
    landmarks = json.loads(request.GET.get('landmarks') or "[7, 30, 90]")
    landmarks.sort()
    now = datetime.utcnow()
    dates = []
    for landmark in landmarks:
        dates.append(now - timedelta(days=landmark))

    domains = Domain.objects.all().order_by("name")

    for domain in domains:
        forms = [r['value'] for r in get_db().view('reports/all_submissions',
            reduce=False,
            startkey=[domain.name, json_format_datetime(dates[-1])],
            endkey=[domain.name, json_format_datetime(now)],
        ).all()]
        domain.user_sets = [dict() for landmark in landmarks]
        domain.users = dict([(user.user_id, user) for user in CommCareUser.by_domain(domain.name)])

        for form in forms:
            user_id = form.get('user_id')
            time = string_to_datetime(form['time']).replace(tzinfo = None)
            if user_id in domain.users:
                for i, date in enumerate(dates):
                    if time > date:
                        domain.user_sets[i][user_id] = domain.users[user_id]
    return render_to_response(request, template, {
        'domains': domains,
        'landmarks': landmarks
    })