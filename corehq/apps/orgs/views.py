from datetime import datetime
from couchdbkit import ResourceNotFound
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpResponseForbidden
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.hqwebapp.utils import InvitationView
from corehq.apps.orgs.decorators import org_admin_required, org_member_required
from corehq.apps.registration.forms import DomainRegistrationForm
from corehq.apps.orgs.forms import AddProjectForm, InviteMemberForm, AddTeamForm, UpdateOrgInfo
from corehq.apps.users.models import WebUser, UserRole, OrgRemovalRecord
from dimagi.utils.web import render_to_response, json_response
from corehq.apps.orgs.models import Organization, Team, DeleteTeamRecord, OrgInvitation, OrgRequest
from corehq.apps.domain.models import Domain
from django.contrib import messages


@require_superuser
def orgs_base(request, template="orgs/orgs_base.html"):
    organizations = Organization.get_all()
    vals = dict(orgs = organizations)
    return render_to_response(request, template, vals)

@org_member_required
def orgs_landing(request, org, template="orgs/orgs_landing.html", form=None, add_form=None, invite_member_form=None,
                 add_team_form=None, update_form=None):
    organization = Organization.get_by_name(org, strict=True)

    reg_form_empty = not form
    add_form_empty = not add_form
    invite_member_form_empty = not invite_member_form
    add_team_form_empty = not add_team_form
    update_form_empty = not update_form

    reg_form = form or DomainRegistrationForm(initial={'org': organization.name})
    add_form = add_form or AddProjectForm(org)
    invite_member_form = invite_member_form or InviteMemberForm(org)
    add_team_form = add_team_form or AddTeamForm(org)

    update_form = update_form or UpdateOrgInfo(initial={'org_title': organization.title, 'email': organization.email,
                                                        'url': organization.url, 'location': organization.location})

    current_teams = Team.get_by_org(org)
    current_domains = Domain.get_by_organization(org).all()
    members = organization.get_members()
    admin = request.couch_user.is_org_admin(org) or request.couch_user.is_superuser

    # display a notification for each org request that hasn't previously been seen
    if request.couch_user.is_org_admin(org):
        for req in OrgRequest.get_requests(org):
            if req.seen or req.domain in [d.name for d in current_domains]:
                continue
            messages.info(request, render_to_string("orgs/partials/org_request_notification.html",
                {"requesting_user": WebUser.get(req.requested_by).username, "org_req": req, "org": organization}),
                extra_tags="html")

    vals = dict(org=organization, domains=current_domains, reg_form=reg_form, add_form=add_form,
                reg_form_empty=reg_form_empty, add_form_empty=add_form_empty, update_form=update_form,
                update_form_empty=update_form_empty, invite_member_form=invite_member_form,
                invite_member_form_empty=invite_member_form_empty, add_team_form=add_team_form,
                add_team_form_empty=add_team_form_empty, teams=current_teams, members=members, admin=admin)
    return render_to_response(request, template, vals)

@require_superuser
def get_data(request, org):
    organization = Organization.get_by_name(org)
    return json_response(organization)

@org_admin_required
@require_POST
def orgs_new_project(request, org):
    from corehq.apps.registration.views import register_domain
    return register_domain(request)

@org_admin_required
@require_POST
def orgs_update_info(request, org):
    organization = Organization.get_by_name(org)
    form = UpdateOrgInfo(request.POST, request.FILES)
    if form.is_valid():
        logo = None
        if form.cleaned_data['org_title'] or organization.title:
            organization.title = form.cleaned_data['org_title']
        if form.cleaned_data['email'] or organization.email:
            organization.email = form.cleaned_data['email']
        if form.cleaned_data['url'] or organization.url:
            organization.url = form.cleaned_data['url']
        if form.cleaned_data['location'] or organization.location:
            organization.location = form.cleaned_data['location']
            #logo not working, need to look into this
        if form.cleaned_data['logo']:
            logo = form.cleaned_data['logo']
            if organization.logo_filename:
                organization.delete_attachment(organization.logo_filename)
                organization.logo_filename = logo.name

        organization.save()
        if logo:
            organization.put_attachment(content=logo.read(), name=logo.name)
    else:
        return orgs_landing(request, org, update_form=form)

@org_admin_required
@require_POST
def orgs_add_project(request, org):
    form = AddProjectForm(org, request.POST)
    if form.is_valid():
        domain_name = form.cleaned_data['domain_name']

        if not request.couch_user.is_domain_admin(domain_name):
            org_requests = filter(lambda r: r.domain == domain_name, OrgRequest.get_requests(org))
            if not org_requests:
                messages.error(request, 'You must be an admin of this project in order to add it to your organization')
                return orgs_landing(request, org, add_form=form)

        dom = Domain.get_by_name(domain_name)
        dom.organization = org
        dom.slug = form.cleaned_data['domain_slug']
        dom.save()
        messages.success(request, "Project Added!")
    else:
        messages.error(request, "Unable to add project")
        return orgs_landing(request, org, add_form=form)
    return HttpResponseRedirect(reverse('orgs_landing', args=[org]))

@org_admin_required
@require_POST
def invite_member(request, org):
    form = InviteMemberForm(org, request.POST)
    if form.is_valid():
        data = form.cleaned_data
        data["invited_by"] = request.couch_user.user_id
        data["invited_on"] = datetime.utcnow()
        data["organization"] = org
        invite = OrgInvitation(**data)
        invite.save()
        invite.send_activation_email()
        messages.success(request, "Invitation sent to %s" % invite.email)
    else:
        messages.error(request, "Unable to add member")
        return orgs_landing(request, org, invite_member_form=form)
    return HttpResponseRedirect(reverse('orgs_landing', args=[org]))

class OrgInvitationView(InvitationView):
    inv_type = OrgInvitation
    template = "orgs/orgs_accept_invite.html"
    need = ["organization"]

    def added_context(self):
        return {'organization': self.organization}

    def validate_invitation(self, invitation):
        assert invitation.organization == self.organization

    @property
    def success_msg(self):
        return "You have been added to the %s organization" % self.organization

    @property
    def redirect_to_on_success(self):
        return reverse("orgs_landing", args=[self.organization,])

    def invite(self, invitation, user):
        user.add_org_membership(self.organization)
        user.save()

@transaction.commit_on_success
def accept_invitation(request, org, invitation_id):
    return OrgInvitationView()(request, invitation_id, organization=org)

@org_admin_required
@require_POST
def orgs_add_team(request, org):
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

@org_member_required
def orgs_logo(request, org, template="orgs/orgs_logo.html"):
    organization = Organization.get_by_name(org)
    if organization.logo_filename:
        image = organization.get_logo()
    else:
        image = None
    return HttpResponse(image, content_type='image/gif')

@org_member_required
def orgs_teams(request, org, template="orgs/orgs_teams.html"):
    organization = Organization.get_by_name(org)
    teams = Team.get_by_org(org)
    current_domains = Domain.get_by_organization(org).all()
    vals = dict(org=organization, teams=teams, domains=current_domains)
    return render_to_response(request, template, vals)

@org_member_required
def orgs_team_members(request, org, team_id, template="orgs/orgs_team_members.html"):
    #organization and teams
    organization = Organization.get_by_name(org)
    teams = Team.get_by_org(org)
    current_domains = Domain.get_by_organization(org).all()

    try:
        team = Team.get(team_id)
    except ResourceNotFound:
        raise Http404("Team %s does not exist" % team_id)

    members = team.get_members()
    members.sort(key=lambda user: user.username)

    #inspect the domains of the team
    domain_names = team.get_domains()
    domains = list()
    for name in domain_names:
        domains.append([Domain.get_by_name(name), team.role_label(domain=name), UserRole.by_domain(name)])

    all_org_domains = Domain.get_by_organization(org).all()
    non_domains = [domain for domain in all_org_domains if domain.name not in domain_names]

    all_org_members = organization.get_members()
    non_members = [member for member in all_org_members if member.user_id not in [m.user_id for m in members]]

    admin = request.couch_user.is_org_admin(org) or request.couch_user.is_superuser

    vals = dict(org=organization, team=team, teams=teams, members=members, nonmembers=non_members,
        domains=current_domains, team_domains=domains, team_nondomains=non_domains, admin=admin)
    return render_to_response(request, template, vals)

@org_admin_required
@require_POST
def add_team(request, org):
    team_name = request.POST['team_name']
    team = Team.get_by_org_and_name(org, team_name)
    if not team:
        team = Team(name=team_name, organization=org)
        team.is_global_admin()
        team.save()
    return HttpResponseRedirect(reverse("orgs_team_members", args=(org, team.get_id)))

@org_admin_required
@require_POST
def join_team(request, org, team_id, couch_user_id):
    user = WebUser.get(couch_user_id)
    user.add_to_team(org, team_id)
    user.save()
    if 'redirect_url' in request.POST:
        return HttpResponseRedirect(reverse(request.POST['redirect_url'], args=(org, team_id)))

@org_admin_required
@require_POST
def leave_team(request, org, team_id, couch_user_id):
    user = WebUser.get(couch_user_id)
    user.remove_from_team(org, team_id)
    user.save()
    if 'redirect_url' in request.POST:
        return HttpResponseRedirect(reverse(request.POST['redirect_url'], args=(org, team_id)))

@org_admin_required
@require_POST
def delete_team(request, org, team_id):
    team = Team.get(team_id)
    if team.organization == org:
        record = team.soft_delete()
        messages.success(request, 'You have deleted a team. <a href="{url}" class="post-link">Undo</a>'.format(
            url=reverse('undo_delete_team', args=[org, record.get_id])
        ), extra_tags="html")
        return HttpResponseRedirect(reverse("orgs_teams", args=(org, )))
    else:
        return HttpResponseForbidden()

@org_admin_required
def undo_delete_team(request, org, record_id):
    record = DeleteTeamRecord.get(record_id)
    record.undo()
    return HttpResponseRedirect(reverse('orgs_team_members', args=[org, record.doc_id]))

@org_admin_required
@require_POST
def add_domain_to_team(request, org, team_id, domain):
    team = Team.get(team_id)
    team.add_domain_membership(domain)
    team.save()
    if 'redirect_url' in request.POST:
        return HttpResponseRedirect(reverse(request.POST['redirect_url'], args=(org, team_id)))

@org_admin_required
@require_POST
def remove_domain_from_team(request, org, team_id, domain):
    team = Team.get(team_id)
    team.delete_domain_membership(domain)
    team.save()
    if 'redirect_url' in request.POST:
        return HttpResponseRedirect(reverse(request.POST['redirect_url'], args=(org, team_id)))

@org_admin_required
@require_POST
def set_team_permission_for_domain(request, org, team_id):
    domain = request.POST.get('domain', None)
    role_label = request.POST.get('role_label', None)

    if domain and role_label:
        team = Team.get(team_id)
        team.set_role(domain, role_label)
        team.save()

        dm = team.get_domain_membership(domain)
        return json_response(UserRole.get(dm.role_id).name if not dm.is_admin else 'Admin')
    return HttpResponseRedirect(reverse('orgs_team_members', args=(org, team_id)))

@org_admin_required
@require_POST
def add_all_to_team(request, org, team_id):
    organization = Organization.get_by_name(org)
    members = organization.get_members()
    for member in members:
        member.add_to_team(org, team_id)
        member.save()
    if 'redirect_url' in request.POST:
        return HttpResponseRedirect(reverse(request.POST['redirect_url'], args=(org, team_id)))

@org_admin_required
@require_POST
def remove_all_from_team(request, org, team_id):
    team = Team.get(team_id)
    members = team.get_members()
    for member in members:
        member.remove_from_team(org, team_id)
        member.save()
    if 'redirect_url' in request.POST:
        return HttpResponseRedirect(reverse(request.POST['redirect_url'], args=(org, team_id)))

def search_orgs(request):
    return json_response([{'title': o.title, 'name': o.name} for o in Organization.get_all()])

@org_admin_required
@require_POST
def seen_request(request, org):
    req_id = request.POST.get('request_id', None)
    org_req = OrgRequest.get(req_id)
    if org_req and org_req.organization == org:
        org_req.seen = True
        org_req.save()
    return HttpResponseRedirect(reverse("orgs_landing", args=[org]))

@org_admin_required
@require_POST
def remove_member(request, org):
    member_id = request.POST.get("member_id", None)
    if member_id == request.couch_user.get_id and not request.couch_user.is_superuser:
        messages.error(request, "You cannot remove yourself from an organization")
    else:
        member = WebUser.get(member_id)
        record = member.delete_org_membership(org, create_record=True)
        member.save()
        messages.success(request, 'You have removed {m} from the organization {o}. <a href="{url}" class="post-link">Undo</a>'.format(
            url=reverse('undo_remove_member', args=[org, record.get_id]), m=member.username, o=org
        ), extra_tags="html")
    return HttpResponseRedirect(reverse("orgs_landing", args=[org]))

@org_admin_required
def undo_remove_member(request, org, record_id):
    record = OrgRemovalRecord.get(record_id)
    record.undo()
    return HttpResponseRedirect(reverse('orgs_landing', args=[org]))

