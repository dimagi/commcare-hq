import json

from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from dimagi.utils.couch import CriticalSection
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.couch.undo import DELETED_SUFFIX

from corehq.apps.groups.models import DeleteGroupRecord, Group
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import CouchUser, HqPermissions
from corehq.apps.users.views.utils import log_user_groups_change
from corehq.privileges import CASE_SHARING_GROUPS
from django_prbac.utils import has_privilege

require_can_edit_groups = require_permission(HqPermissions.edit_groups)


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
    group = Group.by_name(domain, group_name)
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


@require_POST
@require_can_edit_groups
def restore_group(request, domain, group_id):
    group = Group.get(group_id)
    group.doc_type = group.doc_type.rstrip(DELETED_SUFFIX)

    _ensure_case_sharing_privilege(request, group)

    group.save()
    messages.info(request, _('The "{0}" group has been restored.'.format(group.name)))
    return HttpResponseRedirect(
        reverse('group_members', args=[domain, group._id])
    )


@require_can_edit_groups
def edit_group(request, domain, group_id):
    group = Group.get(group_id)
    if group.domain == domain:
        name = request.POST.get('name')
        case_sharing = request.POST.get('case_sharing')
        reporting = request.POST.get('reporting')
        if not name:
            messages.warning(request, _(
                "You tried to remove the group's name, "
                "but every group must have a name so we left it unchanged."
            ))
        elif group.name != name:
            dupe = Group.by_name(domain, name)
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

        _ensure_case_sharing_privilege(request, group)

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
        try:
            updated_data = json.loads(request.POST["group-data"])
        except ValueError:
            messages.error(request, _(
                "Unable to update group data. Please check the key-value mappings and try to update again."
            ))
            return HttpResponseRedirect(request.META['HTTP_REFERER'])
        group.metadata = updated_data

        _ensure_case_sharing_privilege(request, group)

        group.save()
        messages.success(request, _("Group '%s' data updated!") % group.name)
        return HttpResponseRedirect(
            reverse("group_members", args=[domain, group_id])
        )
    else:
        return HttpResponseForbidden()


@require_can_edit_groups
@require_POST
def update_group_membership(request, domain, group_id):
    if not (request.couch_user.can_edit_users_in_groups()
            or request.couch_user.can_edit_commcare_users()):
        return HttpResponseForbidden()
    with CriticalSection(['update-group-membership-%s' % group_id]):
        return _update_group_membership(request, domain, group_id)


def _update_group_membership(request, domain, group_id):
    group = Group.get(group_id)
    if group.domain != domain:
        return HttpResponseForbidden()

    selected_users = request.POST.getlist('selected_ids[]')

    # check to make sure no users were deleted at time of making group
    users = iter_docs(CouchUser.get_db(), selected_users)
    safe_users = [
        CouchUser.wrap_correctly(user) for user in users
        if user['doc_type'] == 'CommCareUser' and user.get('domain') == domain
    ]
    safe_ids = [user.user_id for user in safe_users]
    users_added_ids, users_removed_ids = group.set_user_ids(safe_ids)
    _ensure_case_sharing_privilege(request, group)

    group.save()

    # re-fetch users to get fresh groups
    for updated_user_doc in iter_docs(CouchUser.get_db(), set.union(users_added_ids, users_removed_ids)):
        updated_user = CouchUser.wrap_correctly(updated_user_doc)
        log_user_groups_change(domain, request, updated_user)

    messages.success(request, _("Group %s updated!") % group.name)
    return HttpResponseRedirect(reverse("group_members", args=[domain, group_id]))


def _ensure_case_sharing_privilege(request, group):
    if not has_privilege(request, CASE_SHARING_GROUPS):
        if group.case_sharing:
            group.reporting = True
        group.case_sharing = False
