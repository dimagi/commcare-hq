from django.http import Http404
from django.shortcuts import render

from corehq.apps.groups.models import Group
from corehq.apps.users.models import CouchUser, CommCareUser
from corehq.apps.users.views import _users_context, require_can_edit_commcare_users
from dimagi.utils.excel import alphanumeric_sort_key
from dimagi.utils.web import json_response, get_url_base, get_ip

def _get_sorted_groups(domain):
    return sorted(
        Group.by_domain(domain),
        key=lambda group: alphanumeric_sort_key(group.name)
    )

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
GROUP VIEWS
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
@require_can_edit_commcare_users
def all_groups(request, domain, template="groups/all_groups.html"):
    context = _users_context(request, domain)
    all_groups = _get_sorted_groups(domain)
    context.update({
        'domain': domain,
        'all_groups': all_groups
    })
    return render(request, template, context)

@require_can_edit_commcare_users
def group_members(request, domain, group_id, template="groups/group_members.html"):
    context = _users_context(request, domain)
    all_groups = _get_sorted_groups(domain)
    group = Group.get(group_id)
    if group is None:
        raise Http404("Group %s does not exist" % group_id)
    member_ids = group.get_user_ids()
    members = CouchUser.view("_all_docs", keys=member_ids, include_docs=True).all()
    members.sort(key=lambda user: user.username)
    all_users = CommCareUser.by_domain(domain)
    member_ids = set(member_ids)
    nonmembers = [user for user in all_users if user.user_id not in member_ids]

    context.update({"domain": domain,
                    "group": group,
                    "all_groups": all_groups,
                    "members": members,
                    "nonmembers": nonmembers,
                    })
    return render(request, template, context)

#@require_domain_admin
#def my_groups(request, domain, template="groups/groups.html"):
#    return group_membership(request, domain, request.couch_user._id, template)

@require_can_edit_commcare_users
def group_membership(request, domain, couch_user_id, template="groups/groups.html"):
    context = _users_context(request, domain)
    couch_user = CouchUser.get_by_user_id(couch_user_id, domain)
    if request.method == "POST" and 'group' in request.POST:
        group = request.POST['group']
        group.add_user(couch_user)
        group.save()
        #messages.success(request, '%s joined group %s' % (couch_user.username, group.name))
    
    my_groups = Group.by_user(couch_user_id)
    all_groups = _get_sorted_groups(domain)
    other_groups = []
    for group in all_groups:
        if group.get_id not in [g.get_id for g in my_groups]:
            other_groups.append(group)
            #other_groups = [group for group in all_groups if group not in my_groups]
    context.update({"domain": domain,
                    "groups": my_groups,
                    "other_groups": other_groups,
                    "couch_user":couch_user })
    return render(request, template, context)
