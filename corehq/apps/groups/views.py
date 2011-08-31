from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from corehq.apps.groups.models import Group
from corehq.apps.users.decorators import require_permission

require_can_edit_groups = require_permission('edit-users')

@require_can_edit_groups
def add_group(request, domain):
    group_name = request.POST['group_name']
    group = Group.view("groups/by_name", key=group_name)
    if not group:
        group = Group(name=group_name, domain=domain)
        group.save()
    return HttpResponseRedirect(reverse("all_groups", args=(domain, )))

@require_can_edit_groups
def delete_group(request, domain, group_id):
    group = Group.get(group_id)
    group.delete()
    return HttpResponseRedirect(reverse("all_groups", args=(domain, )))
    
@require_can_edit_groups
def join_group(request, domain, couch_user_id, group_id):
    group = Group.get(group_id)
    if group:
        #couch_user = CouchUser.get(couch_user_id)
        group.add_user(couch_user_id)
        #messages.success(request, 'User "%s" added to group "%s"' % (couch_user.username, group.name))

    if 'redirect_url' in request.POST:
        return HttpResponseRedirect(reverse(request.POST['redirect_url'], args=(domain, group.name)))
    else:
        return HttpResponseRedirect(reverse("group_membership", args=(domain, couch_user_id)))

@require_can_edit_groups
def leave_group(request, domain, group_id, couch_user_id):
    group = Group.get(group_id)
    if group:
        group.remove_user(couch_user_id)
    if 'redirect_url' in request.POST:
        return HttpResponseRedirect(reverse(request.POST['redirect_url'], args=(domain, group.name)))
    else:
        return HttpResponseRedirect(reverse("group_membership", args=(domain, couch_user_id)))
