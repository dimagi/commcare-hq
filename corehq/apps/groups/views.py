from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect
from django.views.decorators.http import require_POST
from corehq.util.webutils import render_to_response
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CouchUser

def all_groups(request, domain, template="groups/all_groups.html"):
    all_groups = Group.view("groups/by_domain", key=domain)
    return render_to_response(request, template, {
        'domain': domain,
        'all_groups': all_groups
    })

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
    
def group_members(request, domain, group_name, template="groups/group_members.html"):
    context = {}
    group = Group.view("groups/by_name", key=group_name).one()
    member_ids = [m['value'] for m in CouchUser.view("users/by_group", key=group.name).all()]
    members = [m for m in CouchUser.view("users/all_users", keys=member_ids).all()]
    commcare_users = []
    for member in members:
        commcare_users.extend([commcare_account for commcare_account in member.commcare_accounts])
    context.update({"domain": domain,
                    "group": group,
                    "members": commcare_users, 
                    })
    return render_to_response(request, template, context)

def my_groups(request, domain, template="groups/groups.html"):
    return group_membership(request, domain, request.couch_user._id, template)

def group_membership(request, domain, couch_user_id, template="groups/groups.html"):
    context = {}
    couch_user = CouchUser.get(couch_user_id)
    if request.method == "POST" and 'group' in request.POST:
        group = request.POST['group']
        group.add_user(couch_user)
        group.save()
        context['status'] = '%s joined group %s' % (couch_user._id, group.name)
    my_groups = Group.view("groups/by_user", key=couch_user_id).all()
    all_groups = Group.view("groups/by_domain", key=domain).all()
    other_groups = []
    for group in all_groups:
        if group.name not in [g.name for g in my_groups]:
            other_groups.append(group)
    #other_groups = [group for group in all_groups if group not in my_groups]
    context.update({"domain": domain,
                    "groups": my_groups, 
                    "other_groups": other_groups,
                    "couch_user":couch_user })
    return render_to_response(request, template, context)

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
