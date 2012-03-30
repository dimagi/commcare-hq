from django.http import HttpResponseRedirect
from corehq.apps.domain.decorators import login_and_domain_required
from django.core.urlresolvers import reverse

@login_and_domain_required
def default(request, domain):
    return HttpResponseRedirect(reverse("users_default", args=[domain]))

@login_and_domain_required
def redirect_users(request, domain):
    return HttpResponseRedirect(reverse("users_default", args=[domain]))

@login_and_domain_required
def redirect_domain_settings(request, domain):
    return HttpResponseRedirect(reverse("domain_global_settings", args=[domain]))