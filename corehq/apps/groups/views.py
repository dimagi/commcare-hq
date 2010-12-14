from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect
from django.views.decorators.http import require_POST
from corehq.util.webutils import render_to_response
from corehq.apps.groups.models import Group

def all_groups(request, domain, template="groups/all_groups.html"):
    all_groups = Group.view("groups/by_domain", key=domain)
    return render_to_response(request, template, {
        'domain': domain,
        'all_groups': all_groups
    })
    
def my_groups(request, domain, template="groups/all_groups.html"):
    return groups(request, domain, request.couch_user.id, template)

def groups(request, domain, couch_id, template="groups/all_groups.html"):
    #groups = Group.view("groups/by_user", key=couch_id)
    groups = Group.view("groups/by_domain", key=domain)
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
