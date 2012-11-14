import json
from corehq.apps.users.models import Permissions
from couchdbkit.exceptions import ResourceConflict
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.views.decorators.http import require_POST
from corehq.apps.groups.models import Group, DeleteGroupRecord
from corehq.apps.users.decorators import require_permission
from dimagi.utils.couch.resource_conflict import repeat

require_can_edit_groups = require_permission(Permissions.edit_commcare_users)

@require_POST
@require_can_edit_groups
def add_group(request, domain):
    group_name = request.POST['group_name']
    group = Group.view("groups/by_name", key=group_name)
    if not group:
        group = Group(name=group_name, domain=domain)
        group.save()
    return HttpResponseRedirect(reverse("group_members", args=(domain, group.get_id)))

@require_POST
@require_can_edit_groups
def delete_group(request, domain, group_id):
    group = Group.get(group_id)
    if group.domain == domain:
        record = group.soft_delete()
        if record:
            messages.success(request, 'You have deleted a group. <a href="{url}" class="post-link">Undo</a>'.format(
                url=reverse('undo_delete_group', args=[domain, record.get_id])
            ), extra_tags="html")
        return HttpResponseRedirect(reverse("all_groups", args=(domain, )))
    else:
        return HttpResponseForbidden()

@require_POST
@require_can_edit_groups
def undo_delete_group(request, domain, record_id):
    record = DeleteGroupRecord.get(record_id)
    record.undo()
    return HttpResponseRedirect(reverse('group_members', args=[domain, record.doc_id]))

@require_can_edit_groups
def edit_group(request, domain, group_id):
    group = Group.get(group_id)
    if group.domain == domain:
        name = request.POST.get('name')
        case_sharing = request.POST.get('case_sharing')
        reporting = request.POST.get('reporting')
        if name is not None:
            group.name = name
        if case_sharing in ('true', 'false'):
            group.case_sharing = json.loads(case_sharing)
        if reporting in ('true', 'false'):
            group.reporting = json.loads(reporting)
        group.save()
        return HttpResponseRedirect(reverse("group_members", args=[domain, group_id]))
    else:
        return HttpResponseForbidden()

@require_can_edit_groups
def join_group(request, domain, group_id, couch_user_id):
    def add_user():
        group = Group.get(group_id)
        if group:
                group.add_user(couch_user_id)
    repeat(add_user, 3)
    if 'redirect_url' in request.POST:
        return HttpResponseRedirect(reverse(request.POST['redirect_url'], args=(domain, group_id)))
    else:
        return HttpResponseRedirect(reverse("group_membership", args=(domain, couch_user_id)))

@require_can_edit_groups
def leave_group(request, domain, group_id, couch_user_id):
    def remove_user():
        group = Group.get(group_id)
        if group:
            group.remove_user(couch_user_id)
    repeat(remove_user, 3)
    if 'redirect_url' in request.POST:
        return HttpResponseRedirect(reverse(request.POST['redirect_url'], args=(domain, group_id)))
    else:
        return HttpResponseRedirect(reverse("group_membership", args=(domain, couch_user_id)))
