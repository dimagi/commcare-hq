from dimagi.utils.web import render_to_response, json_response, get_url_base
from corehq.apps.orgs.models import Organization

def orgs_base(request, template="orgs/orgs_front.html"):
    orgs = Organization
    return render_to_response(request, template)


def orgs_landing(request, org, template="orgs/orgs_landing.html"):
    organization = Organization.get_by_name(org)
    vals = dict(name=organization.name, title=organization.title)
    return render_to_response(request, template, vals)
