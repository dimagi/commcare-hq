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
    #groups = Group.view("groups/by_user", key=couch_id)
    my_groups = Group.view("groups/by_domain", key=domain)
    other_groups = Group.view("groups/by_domain", key=domain)
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
        group.save()
    return HttpResponseRedirect(reverse("group_membership", args=(domain, couch_user_id)))

@require_POST
def leave_group(request, domain, couch_user_id, group_id):
    group = Group.get(group_id)
    if group:
        group.remove_user(couch_user_id)
        group.save()
    return HttpResponseRedirect(reverse("group_membership", args=(domain, couch_user_id )))
