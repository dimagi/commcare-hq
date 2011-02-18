from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import permission_required
from django.template.context import RequestContext
from corehq.apps.domain.models import Domain
from dimagi.utils.couch.database import get_db
from collections import defaultdict
from corehq.apps.domain.decorators import login_and_domain_required

@permission_required("is_superuser")
def default(request):
    return HttpResponseRedirect(reverse("domain_list"))

@permission_required("is_superuser")
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
    