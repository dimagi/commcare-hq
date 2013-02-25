from django.http import HttpResponseRedirect, HttpResponse, Http404
from corehq.apps.domain.decorators import login_and_domain_required, require_superuser, login_required_late_eval_of_LOGIN_URL
from django.core.urlresolvers import reverse
from dimagi.utils.web import json_response

@login_and_domain_required
def default(request, domain):
    return HttpResponseRedirect(reverse("users_default", args=[domain]))

@login_and_domain_required
def redirect_users(request, domain, old_url=""):
    return HttpResponseRedirect(reverse("users_default", args=[domain]))

@login_and_domain_required
def redirect_domain_settings(request, domain, old_url=""):
    return HttpResponseRedirect(reverse("domain_forwarding", args=[domain]))

@login_required_late_eval_of_LOGIN_URL
def account_settings(request):
    # tabling this until HQ Announcements is flushed out.
    raise Http404

@require_superuser
def project_id_mapping(request, domain):
    from corehq.apps.users.models import CommCareUser
    from corehq.apps.groups.models import Group

    users = CommCareUser.by_domain(domain)
    groups = Group.by_domain(domain)

#    return json_response({
#        'users': [{'name': user.raw_username, 'id': user.user_id} for user in users],
#        'groups': [{'name': group.name, 'id': group.get_id} for group in groups],
#    })
    return json_response({
        'users': dict([(user.raw_username, user.user_id) for user in users]),
        'groups': dict([(group.name, group.get_id) for group in groups]),
    })