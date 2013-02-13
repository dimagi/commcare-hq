import json

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.utils.translation import ugettext as _

from corehq.apps.users.models import Permissions
from corehq.apps.groups.models import Group, DeleteGroupRecord
from corehq.apps.users.decorators import require_permission
from dimagi.utils.couch.resource_conflict import repeat


require_can_edit_groups = require_permission(Permissions.edit_commcare_users)

@require_POST
@require_can_edit_groups
def add_group(request, domain):
    group_name = request.POST['group_name']
    if not group_name:
        messages.error(request, _(
            "We could not create the group; "
            "please give it a name first"
        ))
        return HttpResponseRedirect(request.META['HTTP_REFERER'])
    group = Group.by_name(domain, group_name, one=False).first()
    if group:
        messages.warning(request, _(
            "A group with this name already exists: instead of making "
            "a new one, we've brought you to the existing one."
        ))
    else:
        group = Group(name=group_name, domain=domain)
        group.save()

    return HttpResponseRedirect(
        reverse("group_members", args=(domain, group.get_id))
    )

@require_POST
@require_can_edit_groups
def delete_group(request, domain, group_id):
    group = Group.get(group_id)
    if group.domain == domain:
        record = group.soft_delete()
        if record:
            messages.success(request, _(
                "You have deleted a group. "
                '<a href="{url}" class="post-link">Undo</a>'
            ).format(
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
    return HttpResponseRedirect(
        reverse('group_members', args=[domain, record.doc_id])
    )

@require_can_edit_groups
def edit_group(request, domain, group_id):
    group = Group.get(group_id)
    if group.domain == domain:
        name = request.POST.get('name')
        case_sharing = request.POST.get('case_sharing')
        reporting = request.POST.get('reporting')
        if name is not None and group.name != name:
            dupe = Group.by_name(domain, name, one=False).first()
            if dupe:
                messages.warning(request, _(
                    "We didn't rename your group because there's already "
                    "another group with that name."
                ))
            else:
                group.name = name
        if case_sharing in ('true', 'false'):
            group.case_sharing = json.loads(case_sharing)
        if reporting in ('true', 'false'):
            group.reporting = json.loads(reporting)
        group.save()
        return HttpResponseRedirect(
            reverse("group_members", args=[domain, group_id])
        )
    else:
        return HttpResponseForbidden()

@require_can_edit_groups
@require_POST
def update_group_data(request, domain, group_id):
    group = Group.get(group_id)
    if group.domain == domain:
        updated_data = json.loads(request.POST["group-data"])
        group.metadata = updated_data
        group.save()
        messages.success(request, _("Group '%s' data updated!") % group.name)
        return HttpResponseRedirect(
            reverse("group_members", args=[domain, group_id])
        )
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
        return HttpResponseRedirect(
            reverse(request.POST['redirect_url'], args=(domain, group_id))
        )
    else:
        return HttpResponseRedirect(
            reverse("group_membership", args=(domain, couch_user_id))
        )

@require_can_edit_groups
def leave_group(request, domain, group_id, couch_user_id):
    def remove_user():
        group = Group.get(group_id)
        if group:
            group.remove_user(couch_user_id)
    repeat(remove_user, 3)
    if 'redirect_url' in request.POST:
        return HttpResponseRedirect(
            reverse(request.POST['redirect_url'], args=(domain, group_id))
        )
    else:
        return HttpResponseRedirect(
            reverse("group_membership", args=(domain, couch_user_id))
        )
