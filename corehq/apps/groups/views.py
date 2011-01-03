from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.views.decorators.http import require_POST
from corehq.apps.groups.models import Group

@require_POST
def add_group(request, domain):
    group_name = request.POST['group_name']
    group = Group.view("groups/by_name", key=group_name)
    if not group:
        group = Group(name=group_name, domain=domain)
        group.save()
    return HttpResponseRedirect(reverse("all_groups", args=(domain, )))

@require_POST
def delete_group(request, domain, group_id):
    group = Group.get(group_id)
    group.delete()
    return HttpResponseRedirect(reverse("all_groups", args=(domain, )))
    
@require_POST
def join_group(request, domain, couch_user_id, group_id):
    group = Group.get(group_id)
    if group:
        group.add_user(couch_user_id)
    if 'redirect_url' in request.POST:
        return HttpResponseRedirect(reverse(request.POST['redirect_url'], args=(domain, group.name)))
    else:
        return HttpResponseRedirect(reverse("group_membership", args=(domain, couch_user_id)))

@require_POST
def leave_group(request, domain, group_id, couch_user_id):
    group = Group.get(group_id)
    if group:
        group.remove_user(couch_user_id)
    if 'redirect_url' in request.POST:
        return HttpResponseRedirect(reverse(request.POST['redirect_url'], args=(domain, group.name)))
    else:
        return HttpResponseRedirect(reverse("group_membership", args=(domain, couch_user_id)))
