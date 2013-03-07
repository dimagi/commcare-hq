from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect

def no_permissions_redirect(request):
    np_page = reverse('no_permissions')
    return HttpResponseRedirect(np_page) if request.method == 'GET' else HttpResponse("Missing qualifications")

def org_admin_required(view_func):
    def shim(request, org, *args, **kwargs):
        if not hasattr(request, 'couch_user') or not \
        (request.couch_user.is_org_admin(org) or request.couch_user.is_superuser):
            return no_permissions_redirect(request)
        else:
            return view_func(request, org, *args, **kwargs)
    return shim

def org_member_required(view_func):
    def shim(request, org, *args, **kwargs):
        if not hasattr(request, 'couch_user') or not\
        (request.couch_user.is_member_of_org(org) or request.couch_user.is_superuser):
            return no_permissions_redirect(request)
        else:
            return view_func(request, org, *args, **kwargs)
    return shim
