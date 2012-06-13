from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.registration.forms import DomainRegistrationForm
from dimagi.utils.web import render_to_response, json_response, get_url_base
from corehq.apps.orgs.models import Organization
from corehq.apps.domain.models import Domain
from django.contrib import messages

@require_superuser
def orgs_landing(request, org, template="orgs/orgs_landing.html", form=None):
    organization = Organization.get_by_name(org)
    is_empty = not form
    form = form or DomainRegistrationForm()
    current_domains = Domain.get_by_organization(org)
    vals = dict( org=organization, domains=current_domains, form=form, is_empty=is_empty)
    return render_to_response(request, template, vals)

@require_superuser
def orgs_new_project(request, org):
    from corehq.apps.registration.views import register_domain
    if request.method == 'POST':
        return register_domain(request)
    else:
        return orgs_landing(request, org, form=DomainRegistrationForm())


@require_superuser
def orgs_add_project(request, org):
    if request.method == "POST":
        domain_name = request.POST['domain_name']
        if domain_name == '':
            #put an error message saying that user needs to enter a field
            messages.error(request, "Please enter a project name")
        elif Domain.get_by_name(domain_name):
            dom = Domain.get_by_name(domain_name)
            dom.organization = org
            dom.save()
            messages.success(request, "Project added!")
        else:
            #put an error message saying that no organization by that name was found
            messages.error(request, "Project not found")
    return HttpResponseRedirect(reverse(orgs_landing, args=[org]))

@require_superuser
def orgs_logo(request, org, template="orgs/orgs_logo.html"):
    organization = Organization.get_by_name(org)
    if organization.logo_filename:
        image = organization.get_logo()
    else:
        image = None
    return HttpResponse(image, content_type='image/gif')