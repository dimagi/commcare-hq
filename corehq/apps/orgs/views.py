from datetime import datetime, timedelta, date
from couchdbkit import ResourceNotFound
from casexml.apps.case.models import CommCareCase
from dimagi.utils.couch.database import get_db
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.shortcuts import render
from django.contrib import messages
from corehq.apps.announcements.models import Notification
from corehq.apps.appstore.views import parse_args_for_es

from corehq.apps.domain.decorators import require_superuser
from corehq.apps.hqwebapp.utils import InvitationView
from corehq.apps.orgs.decorators import org_admin_required, org_member_required
from corehq.apps.registration.forms import DomainRegistrationForm
from corehq.apps.orgs.forms import AddProjectForm, InviteMemberForm, AddTeamForm, UpdateOrgInfo
from corehq.apps.reports.standard.domains import OrgDomainStatsReport
from corehq.apps.users.models import WebUser, UserRole, OrgRemovalRecord
from corehq.elastic import get_es
from corehq.pillows.mappings.case_mapping import CASE_INDEX
from corehq.pillows.mappings.user_mapping import USER_INDEX
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX
from dimagi.utils.decorators.datespan import datespan_in_request
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.parsing import json_format_datetime
from dimagi.utils.web import json_response
from corehq.apps.orgs.models import Organization, Team, DeleteTeamRecord, \
    OrgInvitation, OrgRequest
from corehq.apps.domain.models import Domain
from django.utils.translation import ugettext as _


@memoized
def base_context(request, organization, update_form=None):
    return {
        "org": organization,
        "teams": Team.get_by_org(organization.name),
        "domains": sorted(Domain.get_by_organization(organization.name).all(), key=lambda x: x.name),
        "members": organization.get_members(),
        "admin": request.couch_user.is_org_admin(organization.name) or request.couch_user.is_superuser,
        "update_form_empty": not update_form,
        "update_form": update_form or UpdateOrgInfo(initial={'org_title': organization.title, 'email': organization.email,
                                                            'url': organization.url, 'location': organization.location})
    }

@require_superuser
def orgs_base(request, template="orgs/orgs_base.html"):
    organizations = Organization.get_all()
    vals = dict(orgs = organizations)
    return render(request, template, vals)

class MainNotification(Notification):
    doc_type = 'OrgMainNotification'

    def template(self):
        return 'orgs/partials/main_notification.html'

@org_member_required
def orgs_landing(request, org, template="orgs/orgs_landing.html", form=None, add_form=None, invite_member_form=None,
                 add_team_form=None, update_form=None, tab=None):
    organization = request.organization

    class LandingNotification(Notification):
        doc_type = 'OrgLandingNotification'

        def template(self):
            return 'orgs/partials/landing_notification.html'

    MainNotification.display_if_needed(messages, request, ctxt={"org": organization})
    LandingNotification.display_if_needed(messages, request)

    reg_form_empty = not form
    add_form_empty = not add_form
    invite_member_form_empty = not invite_member_form
    add_team_form_empty = not add_team_form

    reg_form = form or DomainRegistrationForm(initial={'org': organization.name})
    add_form = add_form or AddProjectForm(org)
    invite_member_form = invite_member_form or InviteMemberForm(org)
    add_team_form = add_team_form or AddTeamForm(org)

    ctxt = base_context(request, organization, update_form=update_form)
    user_domains = []
    req_domains = []
    # display a notification for each org request that hasn't previously been seen
    if request.couch_user.is_org_admin(org):
        requests = OrgRequest.get_requests(org)
        for req in requests:
            if req.seen or req.domain in [d.name for d in ctxt["domains"]]:
                continue
            messages.info(request, render_to_string("orgs/partials/org_request_notification.html",
                {"requesting_user": WebUser.get(req.requested_by).username, "org_req": req, "org": organization}),
                extra_tags="html")

        def format_domains(dom_list, extra=None):
            extra = extra or []
            dom_list = list(set(filter(lambda d: d not in ctxt["domains"] + extra, dom_list)))
            return [Domain.get_by_name(d) for d in dom_list]

        # get the existing domains that an org admin would add to the organization
        user_domains = request.couch_user.domains or []
        req_domains = [req.domain for req in requests]
        user_domains = format_domains(user_domains)
        req_domains = format_domains(req_domains, [d.name for d in user_domains if d])

    ctxt.update(dict(reg_form=reg_form, add_form=add_form, reg_form_empty=reg_form_empty, add_form_empty=add_form_empty,
                invite_member_form=invite_member_form, invite_member_form_empty=invite_member_form_empty,
                add_team_form=add_team_form, add_team_form_empty=add_team_form_empty, tab="projects",
                user_domains=user_domains, req_domains=req_domains))
    return render(request, template, ctxt)

@org_member_required
def orgs_members(request, org, template="orgs/orgs_members.html"):
    class MembersNotification(Notification):
        doc_type = 'OrgMembersNotification'

        def template(self):
            return 'orgs/partials/members_notification.html'

    MainNotification.display_if_needed(messages, request, ctxt={"org": request.organization})
    MembersNotification.display_if_needed(messages, request)

    ctxt = base_context(request, request.organization)
    ctxt["org_admins"] = [member.username for member in ctxt["members"] if member.is_org_admin(org)]
    ctxt["tab"] = "members"

    return render(request, template, ctxt)

@org_member_required
def orgs_teams(request, org, template="orgs/orgs_teams.html"):
    class TeamsNotification(Notification):
        doc_type = 'OrgTeamsNotification'

        def template(self):
            return 'orgs/partials/teams_notification.html'

    MainNotification.display_if_needed(messages, request, ctxt={"org": request.organization})
    TeamsNotification.display_if_needed(messages, request)

    ctxt = base_context(request, request.organization)
    ctxt["tab"] = "teams"

    return render(request, template, ctxt)

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
    organization = request.organization
    form = UpdateOrgInfo(request.POST, request.FILES)
    if form.is_valid():
        if form.cleaned_data['org_title'] or organization.title:
            organization.title = form.cleaned_data['org_title']
        if form.cleaned_data['email'] or organization.email:
            organization.email = form.cleaned_data['email']
        if form.cleaned_data['url'] or organization.url:
            organization.url = form.cleaned_data['url']
        if form.cleaned_data['location'] or organization.location:
            organization.location = form.cleaned_data['location']

        organization.save()
        return HttpResponseRedirect(request.META.get('HTTP_REFERER') or reverse('orgs_landing', args=[org]))
    else:
        return orgs_landing(request, org, update_form=form)

@org_admin_required
@require_POST
def orgs_update_project(request, org):
    domain = Domain.get_by_name(request.POST.get('domain', ""))
    new_hr_name = request.POST.get('hr_name', "")
    if domain and new_hr_name:
        if domain.organization != org:
            messages.error(request, "The project %s isn't a part of this organization" % domain.name)
        else:
            old_hr_name = domain.hr_name
            domain.hr_name = new_hr_name
            domain.save()
            messages.success(request, "The projects display name has been changed from %s to %s" % (old_hr_name, new_hr_name))
    else:
        messages.error(request, "Could not edit project information -- missing new display name")

    return HttpResponseRedirect(reverse("orgs_landing", args=(org, )))

@org_admin_required
@require_POST
def orgs_update_team(request, org):
    team_id = request.POST.get('team_id', "")
    new_team_name = request.POST.get('team_name', "")
    if team_id and new_team_name:
        team = Team.get(team_id)
        old_team_name = team.name
        team.name = new_team_name
        team.save()
        messages.success(request, "Team %s has been renamed to %s" % (old_team_name, team.name))
    else:
        messages.error(request, "Could not edit team information -- missing new team name")

    return HttpResponseRedirect(reverse('orgs_team_members', args=(org, team_id)))

@org_admin_required
@require_POST
def orgs_add_project(request, org):
    form = AddProjectForm(org, request.couch_user, request.POST)
    if form.is_valid():
        domain_name = form.cleaned_data['domain_name']

        dom = Domain.get_by_name(domain_name)
        dom.organization = org
        dom.hr_name = form.cleaned_data['domain_hrname']
        dom.save()
        messages.success(request, "Project Added!")
    else:
        messages.error(request, "Unable to add project")
        return orgs_landing(request, org, add_form=form)
    return HttpResponseRedirect(reverse('orgs_landing', args=[org]))

@org_admin_required
@require_POST
def orgs_remove_project(request, org):
    domain = request.POST.get("project_name", None)
    if not domain:
        messages.error(request, "You must specify a project name")
    else:
        domain = Domain.get_by_name(domain)
        domain.organization = None
        domain.save()
        messages.success(request, render_to_string('orgs/partials/undo_remove_project.html',
                                                   {"org": org, "dom": domain}), extra_tags="html")
    return HttpResponseRedirect(reverse(request.POST.get('redirect_url', 'orgs_landing'), args=(org,)))

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
    return HttpResponseRedirect(reverse('orgs_members', args=[org]))

class OrgInvitationView(InvitationView):
    inv_type = OrgInvitation
    template = "orgs/orgs_accept_invite.html"
    need = ["organization"]

    def added_context(self):
        return {'organization': self.organization}

    def validate_invitation(self, invitation):
        assert invitation.organization == self.organization

    def is_invited(self, invitation, couch_user):
        return couch_user.is_member_of_org(invitation.organization)

    @property
    def inviting_entity(self):
        return self.organization

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
    team_name = request.POST.get("team", None)
    if not team_name:
        messages.error(request, 'You must specify a team name')
        return HttpResponseRedirect(reverse('orgs_teams', args=[org]))

    org_teams = Team.get_by_org(org)
    for t in org_teams:
        if t.name == team_name:
            messages.error(request, 'A team with that name already exists.')
            return HttpResponseRedirect(reverse('orgs_teams', args=[org]))

    team = Team(name=team_name, organization=org)
    team.save()
    messages.success(request, "Team Added!")
    return HttpResponseRedirect(reverse('orgs_teams', args=[org]))

@org_member_required
def orgs_logo(request, org, template="orgs/orgs_logo.html"):
    image, type = request.organization.get_logo()
    return HttpResponse(image, content_type=type if image else 'image/gif')

@org_member_required
def orgs_team_members(request, org, team_id, template="orgs/orgs_team_members.html"):
    class TeamMembersNotification(Notification):
        doc_type = 'OrgTeamMembersNotification'

        def template(self):
            return 'orgs/partials/team_members_notification.html'

    MainNotification.display_if_needed(messages, request, ctxt={"org": request.organization})
    TeamMembersNotification.display_if_needed(messages, request)

    ctxt = base_context(request, request.organization)
    ctxt["tab"] = "teams"

    try:
        team = Team.get(team_id)
    except ResourceNotFound:
        raise Http404("Team %s does not exist" % team_id)

    team_members = team.get_members()
    team_members.sort(key=lambda user: user.username)

    #inspect the domains of the team
    domain_names = team.get_domains()
    team_domains = list()
    for name in domain_names:
        team_domains.append([Domain.get_by_name(name), team.role_label(domain=name), UserRole.by_domain(name)])

    nonmembers = filter(lambda m: m.username not in [tm.username for tm in team_members], ctxt["members"])
    nondomains = filter(lambda d: d.name not in [td[0].name for td in team_domains], ctxt["domains"])

    ctxt.update(dict(team=team, team_members=team_members, nonmembers=nonmembers,
                     team_domains=team_domains, nondomains=nondomains))
    return render(request, template, ctxt)

@org_admin_required
@require_POST
def join_team(request, org, team_id):
    username = request.POST.get("username", None)
    if not username:
        messages.error(request, "You must specify a member's email address")
    else:
        user = WebUser.get_by_username(username)
        user.add_to_team(org, team_id)
        user.save()
    return HttpResponseRedirect(reverse(request.POST.get('redirect_url', 'orgs_team_members'), args=(org, team_id)))

@org_admin_required
@require_POST
def leave_team(request, org, team_id):
    username = request.POST.get("username", None)
    if not username:
        messages.error(request, "You must specify a member's email address")
    else:
        user = WebUser.get_by_username(username)
        user.remove_from_team(org, team_id)
        user.save()
        messages.success(request, render_to_string('orgs/partials/undo_leave_team.html',
                                                   {"team_id": team_id, "org": org, "user": user}), extra_tags="html")
    return HttpResponseRedirect(reverse(request.POST.get('redirect_url', 'orgs_team_members'), args=(org, team_id)))

@org_admin_required
@require_POST
def delete_team(request, org):
    team_id = request.POST.get("team_id", None)
    if team_id:
        team = Team.get(team_id)
        # team_name = team.name
        if team.organization == org:
            record = team.soft_delete()
            messages.success(request, 'You have deleted team <strong>{team_name}</strong>. <a href="{url}" class="post-link">Undo</a>'.format(
                team_name=team.name, url=reverse('undo_delete_team', args=[org, record.get_id])
            ), extra_tags="html")
        else:
            messages.error(request, "This team doesn't exist")
    else:
        messages.error(request, "You must specify a team to delete")

    return HttpResponseRedirect(reverse("orgs_teams", args=(org, )))

@org_admin_required
def undo_delete_team(request, org, record_id):
    record = DeleteTeamRecord.get(record_id)
    record.undo()
    return HttpResponseRedirect(reverse('orgs_team_members', args=[org, record.doc_id]))

@org_admin_required
@require_POST
def add_domain_to_team(request, org, team_id):
    domain = request.POST.get("project_name", None)
    if not domain:
        messages.error(request, "You must specify a project name")
    elif domain not in [d.name for d in Domain.get_by_organization(org)]:
        messages.error(request, "You cannot add a domain that isn't managed by this organization")
    else:
        team = Team.get(team_id)
        team.add_domain_membership(domain)
        read_only_role = UserRole.by_domain_and_name(domain, 'Read Only').one()
        team.set_role(domain, 'user-role:%s' % read_only_role.get_id)
        team.save()
    return HttpResponseRedirect(reverse(request.POST.get('redirect_url', 'orgs_team_members'), args=(org, team_id)))


@org_admin_required
@require_POST
def remove_domain_from_team(request, org, team_id):
    domain = request.POST.get("project_name", None)
    if not domain:
        messages.error(request, "You must specify a project name")
    else:
        team = Team.get(team_id)
        team.delete_domain_membership(domain)
        team.save()
        messages.success(request, render_to_string('orgs/partials/undo_remove_domain_from_team.html',
                                                   {"team_id": team_id, "org": org, "dom": domain}), extra_tags="html")
    return HttpResponseRedirect(reverse(request.POST.get('redirect_url', 'orgs_team_members'), args=(org, team_id)))


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
    members = request.organization.get_members()
    for member in members:
        member.add_to_team(org, team_id)
        member.save()
    return HttpResponseRedirect(reverse(request.POST.get('redirect_url', 'orgs_team_members'), args=(org, team_id)))


@org_admin_required
@require_POST
def remove_all_from_team(request, org, team_id):
    team = Team.get(team_id)
    members = team.get_members()
    for member in members:
        member.remove_from_team(org, team_id)
        member.save()
    return HttpResponseRedirect(reverse(request.POST.get('redirect_url', 'orgs_team_members'), args=(org, team_id)))


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
    return HttpResponseRedirect(reverse("orgs_members", args=[org]))

@org_admin_required
def undo_remove_member(request, org, record_id):
    record = OrgRemovalRecord.get(record_id)
    record.undo()
    return HttpResponseRedirect(reverse('orgs_members', args=[org]))

@org_admin_required
def set_admin(request, org):
    member_id = request.POST.get("member_id", None)
    if member_id:
        member = WebUser.get(member_id)
        member.set_org_admin(org)
        member.save()
        messages.success(request, 'You have made %s an admin of the organization %s.' % (member.username, org))
    return HttpResponseRedirect(reverse("orgs_members", args=[org]))

@require_superuser
def verify_org(request, org):
    organization = Organization.get_by_name(org)
    if request.POST.get('verify') == 'true':
        organization.verified = True
        organization.save()
    elif request.POST.get('verify') == 'false':
        organization.verified = False
        organization.save()
    return HttpResponseRedirect(request.META.get('HTTP_REFERER') or reverse('orgs_base'))

def public(request, org, template='orgs/public.html'):
    organization = Organization.get_by_name(org, strict=True)
    ctxt = base_context(request, organization)
    ctxt["snapshots"] = []
    for dom in ctxt["domains"]:
        if dom.published_snapshot() and dom.published_snapshot().is_approved:
            ctxt["snapshots"].append(dom.published_snapshot())
    return render(request, template, ctxt)

@org_member_required
def base_report(request, org, template='orgs/report_base.html'):
    ctxt = base_context(request, request.organization)

    if not ctxt['domains']:
        messages.warning(request, _("This organization has no projects. This report will show no data until a project has been added to the organization."))

    stats_report = OrgDomainStatsReport(request)
    ctxt.update(stats_report.context)

    ctxt.update({
        'tab': 'reports',
        'report_type': 'base',
        'no_header': True if ctxt['domains'] else False,
        'custom_async_url': reverse('basic_report_dispatcher', args=('async/dom_stats',))
    })
    return render(request, template, ctxt)


@org_member_required
@datespan_in_request(from_param="startdate", to_param="enddate")
def stats(request, org, stat_slug, template='orgs/stats.html'):
    ctxt = base_context(request, request.organization)

    xaxis_label = {
        "forms": "# form submissions",
        "cases": "# case creations",
        "users": "# mobile workers created",
    }[stat_slug]

    ctxt.update({
        'tab': 'reports',
        'report_type': 'stats_%s' % stat_slug,
        'no_header': True,
        'stat_slug': stat_slug,
        'xaxis_label': xaxis_label,
        'startdate': request.datespan.startdate_display,
        'enddate': request.datespan.enddate_display,
    })
    return render(request, template, ctxt)

@org_member_required
@datespan_in_request(from_param="startdate", to_param="enddate")
def stats_data(request, org):
    params, _ = parse_args_for_es(request)
    domains = [{"name": d.name, "hr_name": d.hr_name} for d in Domain.get_by_organization(org).all()]
    histo_type = request.GET.get('histogram_type')

    enddate = request.GET.get('enddate')
    enddate = datetime.strptime(enddate, "%Y-%m-%d") if enddate else date.today()
    startdate = request.GET.get('startdate')
    startdate = datetime.strptime(startdate, "%Y-%m-%d") if startdate else enddate - timedelta(days=30)

    histo_data = dict([(d['hr_name'],
                        es_histogram(histo_type, [d["name"]], request.datespan.startdate_display, request.datespan.enddate_display))
                        for d in domains])

    def _total_forms_until_date(dom, date):
        key = ["submission", dom]
        r = get_db().view('reports_forms/all_forms',
            startkey=key+[""],
            endkey=key+[json_format_datetime(date)],
            group=False
        ).one()
        return r['value'] if r else 0

    def _total_cases_until_date(dom, date):
        key = ["", dom]
        r = get_db().view('reports/case_activity',
            startkey=key + [""],
            endkey=key + [json_format_datetime(date), '{}']).one()
        return r['value'] if r else 0

    def _total_users_until_date(dom, date):
        from corehq.apps.appstore.views import es_query
        q = {
            "query": {"term": {"domain": dom}},
            "filter": {
                "and": [
                    {"range": {"created_on": {"lt": date.strftime('%Y-%m-%d')}}},
                    {"term": {"doc_type": "CommCareUser"}},
                ],
            },
        }
        return es_query(q=q, es_url=USER_INDEX + '/user/_search')["hits"]["total"]


    init_val_fn = {
        "forms": _total_forms_until_date,
        "cases": _total_cases_until_date,
        "users": _total_users_until_date,
    }[histo_type]

    return json_response({
        'histo_data': histo_data,
        'initial_values': dict([(dom["name"], init_val_fn(dom["name"], startdate)) for dom in domains]),
        'startdate': request.datespan.startdate_key_utc,
        'enddate': request.datespan.enddate_key_utc,
    })

def es_histogram(histo_type, domains=None, startdate=None, enddate=None, tz_diff=None):
    date_field = {  "forms": "received_on",
                    "cases": "opened_on",
                    "users": "created_on", }[histo_type]
    es_url = {  "forms": XFORM_INDEX + '/xform/_search',
                "cases": CASE_INDEX + '/case/_search',
                "users": USER_INDEX + '/user/_search' }[histo_type]

    q = {"query": {"match_all":{}}}

    if domains is not None:
        q["query"] = {"in" : {"domain.exact": domains}}

    q.update({
        "facets": {
            "histo": {
                "date_histogram": {
                    "field": date_field,
                    "interval": "day"
                },
                "facet_filter": {
                    "and": [{
                        "range": {
                            date_field: {
                                "from": startdate,
                                "to": enddate
                            }}}]}}},
        "size": 0
    })

    if tz_diff:
        q["facets"]["histo"]["date_histogram"]["time_zone"] = tz_diff

    if histo_type == "forms":
        q["facets"]["histo"]["facet_filter"]["and"].append({"not": {"in": {"doc_type": ["xformduplicate", "xformdeleted"]}}})
        q["facets"]["histo"]["facet_filter"]["and"].append({"not": {"missing": {"field": "xmlns"}}})
        q["facets"]["histo"]["facet_filter"]["and"].append({"not": {"missing": {"field": "form.meta.userID"}}})

    if histo_type == "users":
        q["facets"]["histo"]["facet_filter"]["and"].append({"term": {"doc_type": "CommCareUser"}})

    es = get_es()
    ret_data = es.get(es_url, data=q)
    return ret_data["facets"]["histo"]["entries"]
