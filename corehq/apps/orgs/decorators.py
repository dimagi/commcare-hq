from django.core.urlresolvers import reverse
from django.http import HttpResponse

def org_admin_required(view_func):
    def shim(request, org, *args, **kwargs):
        if not hasattr(request, 'couch_user') or not \
        (request.couch_user.is_org_admin(org) or request.couch_user.is_superuser):
            return reverse('no_permissions') if request.method == 'GET' else HttpResponse("Missing qualifications")
        else:
            return view_func(request, org, *args, **kwargs)
    return shim

def org_member_required(view_func):
    def shim(request, org, *args, **kwargs):
        if not hasattr(request, 'couch_user') or not\
        (request.couch_user.is_member_of_org(org) or request.couch_user.is_superuser):
            return reverse('no_permissions') if request.method == 'GET' else HttpResponse("Missing qualifications")
        else:
            return view_func(request, org, *args, **kwargs)
    return shim
