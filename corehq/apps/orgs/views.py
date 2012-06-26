from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.registration.forms import DomainRegistrationForm
from corehq.apps.orgs.forms import AddProjectForm, AddMemberForm, AddTeamForm
from corehq.apps.users.models import CouchUser
from dimagi.utils.web import render_to_response, json_response, get_url_base
from corehq.apps.orgs.models import Organization, Team
from corehq.apps.domain.models import Domain
from django.contrib import messages

@require_superuser
def orgs_base(request, template="orgs/orgs_base.html"):
    organizations = Organization.get_all()
    vals = dict(orgs = organizations)
    return render_to_response(request, template, vals)

@require_superuser
def orgs_landing(request, org, template="orgs/orgs_landing.html", form=None, add_form=None, add_member_form=None, add_team_form=None):
    organization = Organization.get_by_name(org)

    reg_form_empty = not form
    add_form_empty = not add_form
    add_member_form_empty = not add_member_form
    add_team_form_empty = not add_team_form

    reg_form = form or DomainRegistrationForm(initial={'org': organization.name})
    add_form = add_form or AddProjectForm(org)
    add_member_form = add_member_form or AddMemberForm(org)
    add_team_form = add_team_form or AddTeamForm(org)

    current_teams = Team.get_by_org(org)
    current_domains = Domain.get_by_organization(org)
    vals = dict( org=organization, domains=current_domains, reg_form=reg_form,
                 add_form=add_form, reg_form_empty=reg_form_empty, add_form_empty=add_form_empty, add_member_form=add_member_form, add_member_form_empty=add_member_form_empty, add_team_form=add_team_form, add_team_form_empty=add_team_form_empty, teams=current_teams)
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
        form = AddProjectForm(org, request.POST)
        if form.is_valid():
            domain_name = form.cleaned_data['domain_name']
            dom = Domain.get_by_name(domain_name)
            dom.organization = org
            dom.slug = form.cleaned_data['domain_slug']
            dom.save()
            messages.success(request, "Project Added!")
        else:
            messages.error(request, "Unable to add project")
            return orgs_landing(request, org, add_form=form)
    return HttpResponseRedirect(reverse('orgs_landing', args=[org]))

@require_superuser
def orgs_add_member(request, org):
    if request.method == "POST":
        form = AddMemberForm(org, request.POST)
        if form.is_valid():
            username = form.cleaned_data['member_email']
            user_id = CouchUser.get_by_username(username).userID
            organization = Organization.get_by_name(org)
            organization.add_member(user_id)
            messages.success(request, "Member Added!")
        else:
            messages.error(request, "Unable to add member")
            return orgs_landing(request, org, add_member_form=form)
    return HttpResponseRedirect(reverse('orgs_landing', args=[org]))


@require_superuser
def orgs_add_team(request, org):
    if request.method == "POST":
        form = AddTeamForm(org, request.POST)
        if form.is_valid():
            team_name = form.cleaned_data['team']
            team = Team(name=team_name, organization=org)
            team.save()
            messages.success(request, "Team Added!")
        else:
            messages.error(request, "Unable to add team")
            return orgs_landing(request, org, add_team_form=form)
    return HttpResponseRedirect(reverse('orgs_landing', args=[org]))

@require_superuser
def orgs_logo(request, org, template="orgs/orgs_logo.html"):
    organization = Organization.get_by_name(org)
    if organization.logo_filename:
        image = organization.get_logo()
    else:
        image = None
    return HttpResponse(image, content_type='image/gif')