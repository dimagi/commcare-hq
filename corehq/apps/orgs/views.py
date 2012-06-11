from dimagi.utils.web import render_to_response, json_response, get_url_base
from corehq.apps.orgs.models import Organization
from corehq.apps.domain.models import Domain
from django.contrib import messages

def orgs_base(request, template="orgs/orgs_front.html"):
    orgs = Organization
    return render_to_response(request, template)


def orgs_landing(request, org, template="orgs/orgs_landing.html"):
    organization = Organization.get_by_name(org)
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

    current_domains = Domain.get_by_organization(org)
    vals = dict(name=organization.name, title=organization.title, domains=current_domains, email=organization.email, url=organization.url, location=organization.location)
    return render_to_response(request, template, vals)
