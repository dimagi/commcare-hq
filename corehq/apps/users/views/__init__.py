from __future__ import absolute_import
import json
import re
import urllib
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from djangular.views.mixins import allow_remote_invocation, JSONResponseMixin
from corehq import Domain, privileges, toggles
from corehq.apps.app_manager.models import Application
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.style.decorators import (
    use_bootstrap3,
    use_knockout_js,
)
from corehq.apps.users.decorators import require_can_edit_web_users, require_permission_to_edit_user
from corehq.apps.users.util import smart_query_string
from corehq.elastic import ADD_TO_ES_FILTER, es_query, ES_URLS
from dimagi.utils.decorators.memoized import memoized
from django_prbac.exceptions import PermissionDenied
from django_prbac.utils import has_privilege
import langcodes
from datetime import datetime
from couchdbkit.exceptions import ResourceNotFound

from dimagi.utils.couch.database import get_db
from django.contrib.auth.forms import SetPasswordForm
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.contrib import messages
from django_digest.decorators import httpdigest
from no_exceptions.exceptions import Http403

from dimagi.utils.web import json_response

from corehq.apps.registration.forms import AdminInvitesUserForm
from corehq.apps.hqwebapp.utils import InvitationView
from corehq.apps.translations.models import StandaloneTranslationDoc
from corehq.apps.users.forms import (UpdateUserRoleForm, BaseUserInfoForm, UpdateMyAccountInfoForm, CommtrackUserForm, UpdateUserPermissionForm)
from corehq.apps.users.models import (CouchUser, CommCareUser, WebUser,
                                      DomainRemovalRecord, UserRole, AdminUserRole, DomainInvitation, PublicUser,
                                      DomainMembershipError)
from corehq.apps.domain.decorators import (login_and_domain_required, require_superuser, domain_admin_required)
from corehq.apps.orgs.models import Team
from corehq.apps.reports.util import get_possible_reports
from corehq.apps.sms.verify import (
    initiate_sms_verification_workflow,
    VERIFICATION__ALREADY_IN_USE,
    VERIFICATION__ALREADY_VERIFIED,
    VERIFICATION__RESENT_PENDING,
    VERIFICATION__WORKFLOW_STARTED,
)
from corehq.util.couch import get_document_or_404

from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy


def _users_context(request, domain):
    couch_user = request.couch_user
    web_users = WebUser.by_domain(domain)
    teams = Team.get_by_domain(domain)
    for team in teams:
        for user in team.get_members():
            if user.get_id not in [web_user.get_id for web_user in web_users]:
                user.from_team = True
                web_users.append(user)

    for user in [couch_user] + list(web_users):
        user.current_domain = domain

    return {
        'web_users': web_users,
        'domain': domain,
        'couch_user': couch_user,
    }


class BaseUserSettingsView(BaseDomainView):
    section_name = ugettext_noop("Users")

    @property
    @memoized
    def section_url(self):
        from corehq.apps.users.views import DefaultProjectUserSettingsView
        return reverse(DefaultProjectUserSettingsView.urlname, args=[self.domain])

    @property
    @memoized
    def couch_user(self):
        user = self.request.couch_user
        if user:
            user.current_domain = self.domain
        return user

    @property
    def main_context(self):
        context = super(BaseUserSettingsView, self).main_context
        context.update({
            'couch_user': self.couch_user,
        })
        return context


class DefaultProjectUserSettingsView(BaseUserSettingsView):
    urlname = "users_default"

    @property
    @memoized
    def redirect(self):
        redirect = None
        # good ol' public domain...
        if not isinstance(self.couch_user, PublicUser):
            user = CouchUser.get_by_user_id(self.couch_user._id, self.domain)
            if user:
                if user.has_permission(self.domain, 'edit_commcare_users'):
                    redirect = reverse("commcare_users", args=[self.domain])
                elif user.has_permission(self.domain, 'edit_web_users'):
                    redirect = reverse(
                        get_web_user_list_view(self.request).urlname,
                        args=[self.domain]
                    )
        return redirect

    def get(self, request, *args, **kwargs):
        if not self.redirect:
            raise Http404()
        return HttpResponseRedirect(self.redirect)


class BaseEditUserView(BaseUserSettingsView):
    user_update_form_class = None

    @property
    @memoized
    def page_url(self):
        if self.urlname:
            return reverse(self.urlname, args=[self.domain, self.editable_user_id])

    @property
    def parent_pages(self):
        list_view = get_web_user_list_view(self.request)
        return [{
            'title': list_view.page_title,
            'url': reverse(list_view.urlname, args=[self.domain]),
        }]

    @property
    def editable_user_id(self):
        return self.kwargs.get('couch_user_id')

    @property
    @memoized
    def editable_user(self):
        try:
            return get_document_or_404(WebUser, self.domain, self.editable_user_id)
        except (ResourceNotFound, CouchUser.AccountTypeError):
            raise Http404()

    @property
    def existing_role(self):
        try:
            return (self.editable_user.get_role(self.domain,
                                                include_teams=False).get_qualified_id() or '')
        except DomainMembershipError:
            raise Http404()

    @property
    @memoized
    def form_user_update(self):
        if self.user_update_form_class is None:
            raise NotImplementedError("You must specify a form to update the user!")

        if self.request.method == "POST" and self.request.POST['form_type'] == "update-user":
            return self.user_update_form_class(data=self.request.POST)

        form = self.user_update_form_class()
        form.initialize_form(domain=self.request.domain, existing_user=self.editable_user)
        return form

    @property
    def main_context(self):
        context = super(BaseEditUserView, self).main_context
        context.update({
            'couch_user': self.editable_user,
            'form_user_update': self.form_user_update,
            'phonenumbers': self.editable_user.phone_numbers_extended(self.request.couch_user),
        })
        return context

    @property
    @memoized
    def commtrack_form(self):
        if self.request.method == "POST" and self.request.POST['form_type'] == "commtrack":
            return CommtrackUserForm(self.request.POST, domain=self.domain)

        user_domain_membership = self.editable_user.get_domain_membership(self.domain)
        linked_loc = user_domain_membership.location_id
        linked_prog = user_domain_membership.program_id
        return CommtrackUserForm(
            domain=self.domain,
            initial={'location': linked_loc, 'program_id': linked_prog}
        )

    def update_user(self):
        if self.form_user_update.is_valid():
            old_lang = self.request.couch_user.language
            if self.form_user_update.update_user(existing_user=self.editable_user, domain=self.domain):
                # if editing our own account we should also update the language in the session
                if self.editable_user._id == self.request.couch_user._id:
                    new_lang = self.request.couch_user.language
                    if new_lang != old_lang:
                        self.request.session['django_language'] = new_lang
                return True

    def custom_user_is_valid(self):
        return True

    def post(self, request, *args, **kwargs):
        if self.request.POST['form_type'] == "commtrack":
            self.editable_user.get_domain_membership(self.domain).location_id = self.request.POST['location']
            if self.request.project.commtrack_enabled:
                self.editable_user.get_domain_membership(self.domain).program_id = self.request.POST['program_id']
            self.editable_user.save()
        elif self.request.POST['form_type'] == "update-user":
            if all([self.update_user(), self.custom_user_is_valid()]):
                messages.success(self.request, _('Changes saved for user "%s"') % self.editable_user.username)

        return self.get(request, *args, **kwargs)


class EditWebUserView(BaseEditUserView):
    template_name = "users/edit_web_user.html"
    urlname = "user_account"
    page_title = ugettext_noop("Edit User Role")
    user_update_form_class = UpdateUserRoleForm

    @property
    def user_role_choices(self):
        return UserRole.role_choices(self.domain)

    @property
    @memoized
    def form_user_update(self):
        form = super(EditWebUserView, self).form_user_update
        form.load_roles(current_role=self.existing_role, role_choices=self.user_role_choices)
        return form

    @property
    def form_user_update_permissions(self):
        user = self.editable_user
        is_super_user = user.is_superuser

        return UpdateUserPermissionForm(auto_id=False, initial={'super_user': is_super_user})

    @property
    def main_context(self):
        ctx = super(EditWebUserView, self).main_context
        ctx.update({'form_user_update_permissions': self.form_user_update_permissions})
        return ctx

    @property
    def page_context(self):
        ctx = {
            'form_uneditable': BaseUserInfoForm(),
        }
        if (self.request.project.commtrack_enabled or
                self.request.project.uses_locations):
            ctx.update({'update_form': self.commtrack_form})
        if self.request.couch_user.is_superuser:
            ctx.update({'update_permissions': True})

        return ctx

    @method_decorator(require_can_edit_web_users)
    def dispatch(self, request, *args, **kwargs):
        return super(EditWebUserView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if self.editable_user_id == self.couch_user._id:
            return HttpResponseRedirect(reverse(EditMyAccountDomainView.urlname, args=[self.domain]))
        return super(EditWebUserView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self.request.POST['form_type'] == "update-user-permissions" and request.couch_user.is_superuser:
            is_super_user = True if 'super_user' in self.request.POST and self.request.POST['super_user'] == 'on' else False
            if self.form_user_update_permissions.update_user_permission(couch_user=self.request.couch_user,
                                                                        editable_user=self.editable_user, is_super_user=is_super_user):
                messages.success(self.request, _('Changed system permissions for user "%s"') % self.editable_user.username)
        return super(EditWebUserView, self).post(request, *args, **kwargs)


def get_domain_languages(domain):
    app_languages = [res['key'][1] for res in Application.get_db().view(
        'languages/list',
        startkey=[domain],
        endkey=[domain, {}],
        group='true'
    ).all()]

    translation_doc = StandaloneTranslationDoc.get_obj(domain, 'sms')
    sms_languages = translation_doc.langs if translation_doc else []

    domain_languages = []
    for lang_code in set(app_languages + sms_languages):
        name = langcodes.get_name(lang_code)
        label = u"{} ({})".format(lang_code, name) if name else lang_code
        domain_languages.append((lang_code, label))

    return sorted(domain_languages) or langcodes.get_all_langs_for_select()


class BaseFullEditUserView(BaseEditUserView):
    edit_user_form_title = ""

    @property
    def main_context(self):
        context = super(BaseFullEditUserView, self).main_context
        context.update({
            'edit_user_form_title': self.edit_user_form_title,
        })
        return context

    @property
    @memoized
    def form_user_update(self):
        form = super(BaseFullEditUserView, self).form_user_update
        form.load_language(language_choices=get_domain_languages(self.domain))
        return form

    def post(self, request, *args, **kwargs):
        if self.request.POST['form_type'] == "add-phonenumber":
            phone_number = self.request.POST['phone_number']
            phone_number = re.sub('\s', '', phone_number)
            if re.match(r'\d+$', phone_number):
                self.editable_user.add_phone_number(phone_number)
                self.editable_user.save()
                messages.success(request, _("Phone number added!"))
            else:
                messages.error(request, _("Please enter digits only."))
        return super(BaseFullEditUserView, self).post(request, *args, **kwargs)


class EditMyAccountDomainView(BaseFullEditUserView):
    template_name = "users/edit_full_user.html"
    urlname = "domain_my_account"
    page_title = ugettext_noop("Edit My Information")
    edit_user_form_title = ugettext_noop("My Information")
    user_update_form_class = UpdateMyAccountInfoForm

    @property
    def editable_user_id(self):
        return self.couch_user._id

    @property
    def editable_user(self):
        return self.couch_user

    @property
    @memoized
    def page_url(self):
        if self.urlname:
            return reverse(self.urlname, args=[self.domain])

    @property
    def page_context(self):
        context = {
            'can_use_inbound_sms': domain_has_privilege(self.domain, privileges.INBOUND_SMS),
        }
        if (self.request.project.commtrack_enabled or
                self.request.project.uses_locations):
            context.update({
                'update_form': self.commtrack_form,
            })
        return context

    def get(self, request, *args, **kwargs):
        if self.couch_user.is_commcare_user():
            from corehq.apps.users.views.mobile import EditCommCareUserView
            return HttpResponseRedirect(reverse(EditCommCareUserView.urlname, args=[self.domain, self.editable_user_id]))
        return super(EditMyAccountDomainView, self).get(request, *args, **kwargs)


class NewListWebUsersView(JSONResponseMixin, BaseUserSettingsView):
    template_name = 'users/web_users.b3.html'
    page_title = ugettext_lazy("Web Users & Roles")
    urlname = 'web_users_b3'

    @method_decorator(use_bootstrap3())
    @method_decorator(use_knockout_js())
    @method_decorator(require_can_edit_web_users)
    def dispatch(self, request, *args, **kwargs):
        return super(NewListWebUsersView, self).dispatch(request, *args, **kwargs)

    def query_es(self, limit, skip, query=None):
        is_simple, query = smart_query_string(query or '')

        web_user_filter = [
            {"term": {"user.domain_memberships.domain": self.domain}},
        ]
        web_user_filter.extend(ADD_TO_ES_FILTER['web_users'])

        default_fields = ["username", "last_name", "first_name"]
        q = {
            "query": {"query_string": {
                "query": query,
                "default_operator": "AND",
                "fields": default_fields if is_simple else None
            }},
            "filter": {"and": web_user_filter},
            "sort": {'username.exact': 'asc'},
        }
        return es_query(
            params={}, q=q, es_url=ES_URLS["users"],
            size=limit, start_at=skip,
        )

    def apply_teams_to_users(self, web_users):
        teams = Team.get_by_domain(self.domain)
        for team in teams:
            for user in team.get_members():
                if user.get_id not in [web_user.get_id for web_user in web_users]:
                    user.from_team = True
                    web_users.append(user)
        for user in web_users:
            user.current_domain = self.domain

    @allow_remote_invocation
    def get_users(self, in_data):
        if not isinstance(in_data, dict):
            return {
                'success': False,
                'error': _("Please provide pagination info."),
            }
        try:
            limit = in_data.get('limit', 10)
            page = in_data.get('page', 1)
            skip = limit * (page - 1)
            query = in_data.get('query')

            web_users_query = self.query_es(limit, skip, query=query)
            total = web_users_query.get('hits', {}).get('total', 0)
            results = web_users_query.get('hits', {}).get('hits', [])

            web_users = [WebUser.wrap(w['_source']) for w in results]
            self.apply_teams_to_users(web_users)  # for roles

            def _fmt_result(domain, u):
                return {
                    'email': u.email,
                    'domain': domain,
                    'name': u.full_name,
                    'role': u.role_label(),
                    'phoneNumbers': u.phone_numbers,
                    'id': u.get_id,
                    'editUrl': reverse('user_account', args=[domain, u.get_id]),
                    'removeUrl': (
                        reverse('remove_web_user', args=[domain, u.user_id])
                        if self.request.user.username != u.username else None
                    ),
                }
            web_users_fmt = [_fmt_result(self.domain, u) for u in web_users]

            return {
                'response': {
                    'users': web_users_fmt,
                    'total': total,
                    'page': page,
                    'query': query,
                },
                'success': True,
            }
        except Exception as e:
            return {
                'error': e.message,
                'success': False,
            }

    @property
    @memoized
    def user_roles(self):
        user_roles = [AdminUserRole(domain=self.domain)]
        user_roles.extend(sorted(
            UserRole.by_domain(self.domain),
            key=lambda role: role.name if role.name else u'\uFFFF'
        ))

        #  indicate if a role has assigned users, skip admin role
        for i in range(1, len(user_roles)):
            role = user_roles[i]
            role.__setattr__('hasUsersAssigned',
                             True if len(role.ids_of_assigned_users) > 0 else False)
        return user_roles

    @property
    def can_edit_roles(self):
        return has_privilege(self.request, privileges.ROLE_BASED_ACCESS) \
            and self.couch_user.is_domain_admin

    @property
    @memoized
    def role_labels(self):
        role_labels = {}
        for r in self.user_roles:
            key = 'user-role:%s' % r.get_id if r.get_id else r.get_qualified_id()
            role_labels[key] = r.name
        return role_labels

    @property
    @memoized
    def invitations(self):
        invitations = DomainInvitation.by_domain(self.domain)
        for invitation in invitations:
            invitation.role_label = self.role_labels.get(invitation.role, "")
        return invitations

    @property
    def page_context(self):
        return {
            'user_roles': self.user_roles,
            'can_edit_roles': self.can_edit_roles,
            'default_role': UserRole.get_default(),
            'report_list': get_possible_reports(self.domain),
            'invitations': self.invitations,
            'domain_object': self.domain_object,
            'uses_locations': self.domain_object.uses_locations,
        }


class ListWebUsersView(BaseUserSettingsView):
    template_name = 'users/web_users.html'
    page_title = ugettext_lazy("Web Users & Roles")
    urlname = 'web_users'

    @method_decorator(require_can_edit_web_users)
    def dispatch(self, request, *args, **kwargs):
        return super(ListWebUsersView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def web_users(self):
        web_users = WebUser.by_domain(self.domain)
        teams = Team.get_by_domain(self.domain)
        for team in teams:
            for user in team.get_members():
                if user.get_id not in [web_user.get_id for web_user in web_users]:
                    user.from_team = True
                    web_users.append(user)
        for user in web_users:
            user.current_domain = self.domain
        web_users.sort(key=lambda x: (x.role_label(), x.email))
        return web_users

    @property
    @memoized
    def user_roles(self):
        user_roles = [AdminUserRole(domain=self.domain)]
        user_roles.extend(sorted(UserRole.by_domain(self.domain),
                                 key=lambda role: role.name if role.name else u'\uFFFF'))

        #  indicate if a role has assigned users, skip admin role
        for i in range(1, len(user_roles)):
            role = user_roles[i]
            role.__setattr__('hasUsersAssigned',
                             True if len(role.ids_of_assigned_users) > 0 else False)
        return user_roles

    @property
    def can_edit_roles(self):
        return has_privilege(self.request, privileges.ROLE_BASED_ACCESS) \
            and self.couch_user.is_domain_admin

    @property
    @memoized
    def role_labels(self):
        role_labels = {}
        for r in self.user_roles:
            key = 'user-role:%s' % r.get_id if r.get_id else r.get_qualified_id()
            role_labels[key] = r.name
        return role_labels

    @property
    @memoized
    def invitations(self):
        invitations = DomainInvitation.by_domain(self.domain)
        for invitation in invitations:
            invitation.role_label = self.role_labels.get(invitation.role, "")
        return invitations

    @property
    def page_context(self):
        return {
            'web_users': self.web_users,
            'user_roles': self.user_roles,
            'can_edit_roles': self.can_edit_roles,
            'default_role': UserRole.get_default(),
            'report_list': get_possible_reports(self.domain),
            'invitations': self.invitations,
            'domain_object': self.domain_object,
            'uses_locations': self.domain_object.uses_locations,
        }


def get_web_user_list_view(request):
    if toggles.PAGINATE_WEB_USERS.enabled(request.domain):
        return NewListWebUsersView
    return ListWebUsersView


@require_can_edit_web_users
@require_POST
def remove_web_user(request, domain, couch_user_id):
    user = WebUser.get_by_user_id(couch_user_id, domain)
    # if no user, very likely they just pressed delete twice in rapid succession so
    # don't bother doing anything.
    if user:
        record = user.delete_domain_membership(domain, create_record=True)
        user.save()
        messages.success(request, 'You have successfully removed {username} from your domain. <a href="{url}" class="post-link">Undo</a>'.format(
            username=user.username,
            url=reverse('undo_remove_web_user', args=[domain, record.get_id])
        ), extra_tags="html")

    return HttpResponseRedirect(
        reverse(get_web_user_list_view(request).urlname, args=[domain]))


@require_can_edit_web_users
def undo_remove_web_user(request, domain, record_id):
    record = DomainRemovalRecord.get(record_id)
    record.undo()
    messages.success(request, 'You have successfully restored {username}.'.format(
        username=WebUser.get_by_user_id(record.user_id).username
    ))

    return HttpResponseRedirect(
        reverse(get_web_user_list_view(request).urlname, args=[domain]))


# If any permission less than domain admin were allowed here, having that permission would give you the permission
# to change the permissions of your own role such that you could do anything, and would thus be equivalent to having
# domain admin permissions.
@domain_admin_required
@require_POST
def post_user_role(request, domain):
    if not domain_has_privilege(domain, privileges.ROLE_BASED_ACCESS):
        return json_response({})
    role_data = json.loads(request.body)
    role_data = dict([(p, role_data[p]) for p in set(UserRole.properties().keys() + ['_id', '_rev']) if p in role_data])
    role = UserRole.wrap(role_data)
    role.domain = domain
    if role.get_id:
        old_role = UserRole.get(role.get_id)
        assert(old_role.doc_type == UserRole.__name__)
        assert(old_role.domain == domain)
    role.save()
    role.__setattr__('hasUsersAssigned',
                     True if len(role.ids_of_assigned_users) > 0 else False)
    return json_response(role)


@domain_admin_required
@require_POST
def delete_user_role(request, domain):
    if not domain_has_privilege(domain, privileges.ROLE_BASED_ACCESS):
        return json_response({})
    role_data = json.loads(request.body)
    try:
        role = UserRole.get(role_data["_id"])
    except ResourceNotFound:
        return json_response({})
    copy_id = role._id
    role.delete()
    # return removed id in order to remove it from UI
    return json_response({"_id": copy_id})


class UserInvitationView(InvitationView):
    inv_type = DomainInvitation
    template = "users/accept_invite.html"
    need = ["domain"]

    def added_context(self):
        return {
            'domain': self.domain,
            'invite_type': _('Project'),
        }

    def validate_invitation(self, invitation):
        assert invitation.domain == self.domain

    def is_invited(self, invitation, couch_user):
        return couch_user.is_member_of(invitation.domain)

    @property
    def inviting_entity(self):
        return self.domain

    @property
    def success_msg(self):
        return "You have been added to the %s domain" % self.domain

    @property
    def redirect_to_on_success(self):
        return reverse("domain_homepage", args=[self.domain,])

    def invite(self, invitation, user):
        project = Domain.get_by_name(self.domain)
        user.add_domain_membership(domain=self.domain)
        user.set_role(self.domain, invitation.role)

        if project.commtrack_enabled:
            user.get_domain_membership(self.domain).program_id = invitation.program

        if project.uses_locations:
            user.get_domain_membership(self.domain).location_id = invitation.supply_point
        user.save()


@sensitive_post_parameters('password')
def accept_invitation(request, domain, invitation_id):
    return UserInvitationView()(request, invitation_id, domain=domain)


@require_POST
@require_can_edit_web_users
def reinvite_web_user(request, domain):
    invitation_id = request.POST['invite']
    try:
        invitation = DomainInvitation.get(invitation_id)
        invitation.invited_on = datetime.utcnow()
        invitation.save()
        invitation.send_activation_email()
        return json_response({'response': _("Invitation resent"), 'status': 'ok'})
    except ResourceNotFound:
        return json_response({'response': _("Error while attempting resend"), 'status': 'error'})


@require_POST
@require_can_edit_web_users
def delete_invitation(request, domain):
    invitation_id = request.POST['invite']
    invitation = DomainInvitation.get(invitation_id)
    invitation.delete()
    return json_response({'status': 'ok'})


class BaseManageWebUserView(BaseUserSettingsView):

    @method_decorator(require_can_edit_web_users)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseManageWebUserView, self).dispatch(request, *args, **kwargs)

    @property
    def parent_pages(self):
        list_view = get_web_user_list_view(self.request)
        return [{
            'title': list_view.page_title,
            'url': reverse(list_view.urlname, args=[self.domain]),
        }]


class InviteWebUserView(BaseManageWebUserView):
    template_name = "users/invite_web_user.html"
    urlname = 'invite_web_user'
    page_title = ugettext_noop("Invite Web User to Project")

    @property
    @memoized
    def invite_web_user_form(self):
        role_choices = UserRole.role_choices(self.domain)
        loc = None
        if 'location_id' in self.request.GET:
            from corehq.apps.locations.models import SQLLocation
            loc = SQLLocation.objects.get(location_id=self.request.GET.get('location_id'))
        if self.request.method == 'POST':
            current_users = [user.username for user in WebUser.by_domain(self.domain)]
            pending_invites = [di.email for di in DomainInvitation.by_domain(self.domain)]
            return AdminInvitesUserForm(
                self.request.POST,
                excluded_emails=current_users + pending_invites,
                role_choices=role_choices,
                domain=self.domain
            )
        return AdminInvitesUserForm(role_choices=role_choices, domain=self.domain, location=loc)

    @property
    def page_context(self):
        return {
            'registration_form': self.invite_web_user_form,
        }

    def post(self, request, *args, **kwargs):
        if self.invite_web_user_form.is_valid():
            data = self.invite_web_user_form.cleaned_data
            # create invitation record
            data["invited_by"] = request.couch_user.user_id
            data["invited_on"] = datetime.utcnow()
            data["domain"] = self.domain
            invite = DomainInvitation(**data)
            invite.save()
            invite.send_activation_email()
            messages.success(request, "Invitation sent to %s" % invite.email)
            return HttpResponseRedirect(reverse(
                get_web_user_list_view(self.request).urlname,
                args=[self.domain]
            ))
        return self.get(request, *args, **kwargs)


@require_POST
@require_permission_to_edit_user
def make_phone_number_default(request, domain, couch_user_id):
    user = CouchUser.get_by_user_id(couch_user_id, domain)
    if not user.is_current_web_user(request) and not user.is_commcare_user():
        raise Http404()

    phone_number = request.POST['phone_number']
    if not phone_number:
        return Http404('Must include phone number in request.')

    user.set_default_phone_number(phone_number)
    if user.is_commcare_user():
        from corehq.apps.users.views.mobile import EditCommCareUserView
        redirect = reverse(EditCommCareUserView.urlname, args=[domain, couch_user_id])
    else:
        redirect = reverse(EditMyAccountDomainView.urlname, args=[domain])
    return HttpResponseRedirect(redirect)


@require_POST
@require_permission_to_edit_user
def delete_phone_number(request, domain, couch_user_id):
    user = CouchUser.get_by_user_id(couch_user_id, domain)
    if not user.is_current_web_user(request) and not user.is_commcare_user():
        raise Http404()

    phone_number = request.POST['phone_number']
    if not phone_number:
        return Http404('Must include phone number in request.')

    user.delete_phone_number(phone_number)
    if user.is_commcare_user():
        from corehq.apps.users.views.mobile import EditCommCareUserView
        redirect = reverse(EditCommCareUserView.urlname, args=[domain, couch_user_id])
    else:
        redirect = reverse(EditMyAccountDomainView.urlname, args=[domain])
    return HttpResponseRedirect(redirect)


@require_permission_to_edit_user
def verify_phone_number(request, domain, couch_user_id):
    """
    phone_number cannot be passed in the url due to special characters
    but it can be passed as %-encoded GET parameters
    """
    if 'phone_number' not in request.GET:
        return Http404('Must include phone number in request.')
    phone_number = urllib.unquote(request.GET['phone_number'])
    user = CouchUser.get_by_user_id(couch_user_id, domain)

    result = initiate_sms_verification_workflow(user, phone_number)
    if result == VERIFICATION__ALREADY_IN_USE:
        messages.error(request, _('Cannot start verification workflow. Phone number is already in use.'))
    elif result == VERIFICATION__ALREADY_VERIFIED:
        messages.error(request, _('Phone number is already verified.'))
    elif result == VERIFICATION__RESENT_PENDING:
        messages.success(request, _('Verification message resent.'))
    elif result == VERIFICATION__WORKFLOW_STARTED:
        messages.success(request, _('Verification workflow started.'))

    if user.is_commcare_user():
        from corehq.apps.users.views.mobile import EditCommCareUserView
        redirect = reverse(EditCommCareUserView.urlname, args=[domain, couch_user_id])
    else:
        redirect = reverse(EditMyAccountDomainView.urlname, args=[domain])
    return HttpResponseRedirect(redirect)


@require_superuser
@login_and_domain_required
def domain_accounts(request, domain, couch_user_id, template="users/domain_accounts.html"):
    context = _users_context(request, domain)
    couch_user = WebUser.get_by_user_id(couch_user_id, domain)
    if request.method == "POST" and 'domain' in request.POST:
        domain = request.POST['domain']
        couch_user.add_domain_membership(domain)
        couch_user.save()
        messages.success(request, 'Domain added')
    context.update({"user": request.user})
    return render(request, template, context)


@require_POST
@require_superuser
def add_domain_membership(request, domain, couch_user_id, domain_name):
    user = WebUser.get_by_user_id(couch_user_id, domain)
    if domain_name:
        user.add_domain_membership(domain_name)
        user.save()
    return HttpResponseRedirect(reverse("user_account", args=(domain, couch_user_id)))


@sensitive_post_parameters('new_password1', 'new_password2')
@login_and_domain_required
def change_password(request, domain, login_id, template="users/partial/reset_password.html"):
    # copied from auth's password_change

    commcare_user = CommCareUser.get_by_user_id(login_id, domain)
    json_dump = {}
    if not commcare_user:
        raise Http404()
    django_user = commcare_user.get_django_user()
    if request.method == "POST":
        form = SetPasswordForm(user=django_user, data=request.POST)
        if form.is_valid() and (request.project.password_format() != 'n' or request.POST.get('new_password1').isnumeric()):
            form.save()
            json_dump['status'] = 'OK'
            form = SetPasswordForm(user=django_user)
    else:
        form = SetPasswordForm(user=django_user)
    context = _users_context(request, domain)
    context.update({
        'reset_password_form': form,
    })
    json_dump['formHTML'] = render_to_string(template, context)
    return HttpResponse(json.dumps(json_dump))


@httpdigest
@login_and_domain_required
def test_httpdigest(request, domain):
    return HttpResponse("ok")


@require_superuser
def audit_logs(request, domain):
    usernames = [user.username for user in WebUser.by_domain(domain)]
    data = {}
    for username in usernames:
        data[username] = []
        for doc in get_db().view('auditcare/urlpath_by_user_date',
            startkey=[username],
            endkey=[username, {}],
            include_docs=True,
            wrapper=lambda r: r['doc']
        ).all():
            try:
                (d,) = re.search(r'^/a/([\w\-_\.]+)/', doc['request_path']).groups()
                if d == domain:
                    data[username].append(doc)
            except Exception:
                pass
    return json_response(data)


@domain_admin_required
@require_POST
def location_restriction_for_users(request, domain):
    if not toggles.RESTRICT_WEB_USERS_BY_LOCATION.enabled(request.domain):
        raise Http403()
    project = Domain.get_by_name(domain)
    if "restrict_users" in request.POST:
        project.location_restriction_for_users = json.loads(request.POST["restrict_users"])
    project.save()
    return HttpResponse()
