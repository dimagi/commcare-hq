from datetime import timedelta, datetime
from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import permission_required
from django.template.context import RequestContext
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CouchUser
from dimagi.utils.couch.database import get_db
from collections import defaultdict
from corehq.apps.domain.decorators import login_and_domain_required
from dimagi.utils.parsing import json_format_datetime
from dimagi.utils.web import json_response

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
    webuser_counts.update(dict([(row["key"], row["value"]) for row in get_db().view("users/web_users_by_domain", group=True,group_level=1).all()]))
    commcare_counts.update(dict([(row["key"], row["value"]) for row in get_db().view("users/commcare_users_by_domain", group=True,group_level=1).all()]))
    form_counts.update(dict([(row["key"][0], row["value"]) for row in get_db().view("reports/all_submissions", group=True,group_level=1).all()]))
    for dom in domains:
        dom.web_users = webuser_counts[dom.name]
        dom.commcare_users = commcare_counts[dom.name]
        dom.forms = form_counts[dom.name]
        dom.admins = [row["doc"]["email"] for row in get_db().view("users/admins_by_domain", key=dom.name, reduce=False, include_docs=True).all()]
    return render_to_response("hqadmin/domain_list.html", 
                              {"domains": domains,
                               "domain": request.user.selected_domain.name},
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