from __future__ import absolute_import, unicode_literals

import json
import logging
from datetime import datetime

import langcodes
import six.moves.urllib.error
import six.moves.urllib.parse
import six.moves.urllib.request
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.views import redirect_to_login
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy, ugettext_noop
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_POST

from couchdbkit.exceptions import ResourceNotFound

from corehq.apps.hqwebapp.crispy import make_form_readonly
from django_digest.decorators import httpdigest
from django_otp.plugins.otp_static.models import StaticToken
from django_prbac.utils import has_privilege
from memoized import memoized

from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.analytics.tasks import (
    HUBSPOT_EXISTING_USER_INVITE_FORM,
    HUBSPOT_INVITATION_SENT_FORM,
    HUBSPOT_NEW_USER_INVITE_FORM,
    send_hubspot_form,
    track_workflow,
)
from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
from corehq.apps.cloudcare.dbaccessors import get_cloudcare_apps
from corehq.apps.domain.decorators import (
    domain_admin_required,
    login_and_domain_required,
    require_superuser,
)
from corehq.apps.domain.models import Domain
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.es import AppES
from corehq.apps.es.queries import search_string_query
from corehq.apps.hqwebapp.utils import send_confirmation_email
from corehq.apps.hqwebapp.views import BasePageView, logout
from corehq.apps.locations.permissions import (
    conditionally_location_safe,
    location_safe,
    user_can_access_other_user,
)
from corehq.apps.registration.forms import (
    AdminInvitesUserForm,
    WebUserInvitationForm,
)
from corehq.apps.registration.utils import activate_new_user
from corehq.apps.reports.util import get_possible_reports
from corehq.apps.sms.mixin import BadSMSConfigException
from corehq.apps.sms.verify import (
    VERIFICATION__ALREADY_IN_USE,
    VERIFICATION__ALREADY_VERIFIED,
    VERIFICATION__RESENT_PENDING,
    VERIFICATION__WORKFLOW_STARTED,
    initiate_sms_verification_workflow,
)
from corehq.apps.translations.models import StandaloneTranslationDoc
from corehq.apps.users.decorators import (
    require_can_edit_web_users,
    require_can_edit_or_view_web_users,
    require_permission_to_edit_user,
    require_can_view_roles,
)
from corehq.apps.users.forms import (
    BaseUserInfoForm,
    CommtrackUserForm,
    DomainRequestForm,
    SetUserPasswordForm,
    UpdateUserPermissionForm,
    UpdateUserRoleForm,
)
from corehq.apps.users.landing_pages import get_allowed_landing_pages
from corehq.apps.users.models import (
    AdminUserRole,
    CommCareUser,
    CouchUser,
    DomainMembershipError,
    DomainRemovalRecord,
    DomainRequest,
    Invitation,
    UserRole,
    WebUser,
)
from corehq.elastic import ADD_TO_ES_FILTER, es_query
from corehq.util.couch import get_document_or_404
from corehq.util.view_utils import json_error
from dimagi.utils.couch import CriticalSection
from dimagi.utils.web import json_response


def _is_exempt_from_location_safety(view_fn, *args, **kwargs):
    return toggles.LOCATION_SAFETY_EXEMPTION.enabled(kwargs.get("domain", None))


location_safe_for_ews_ils = conditionally_location_safe(_is_exempt_from_location_safety)


def _users_context(request, domain):
    couch_user = request.couch_user
    web_users = WebUser.by_domain(domain)

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


@location_safe
class DefaultProjectUserSettingsView(BaseUserSettingsView):
    urlname = "users_default"

    @property
    @memoized
    def redirect(self):
        redirect = None
        user = CouchUser.get_by_user_id(self.couch_user._id, self.domain)
        if user:
            if (user.has_permission(self.domain, 'edit_commcare_users')
                    or user.has_permission(self.domain, 'view_commcare_users')):
                from corehq.apps.users.views.mobile import MobileWorkerListView
                redirect = reverse(
                    MobileWorkerListView.urlname,
                    args=[self.domain]
                )

            elif (user.has_permission(self.domain, 'edit_groups')
                    or user.has_permission(self.domain, 'view_groups')):
                from corehq.apps.users.views.mobile import GroupsListView
                redirect = reverse(
                    GroupsListView.urlname,
                    args=[self.domain]
                )

            elif (user.has_permission(self.domain, 'edit_web_users')
                    or user.has_permission(self.domain, 'view_web_users')):
                redirect = reverse(
                    ListWebUsersView.urlname,
                    args=[self.domain]
                )

            elif user.has_permission(self.domain, 'view_roles'):
                from corehq.apps.users.views import ListRolesView
                redirect = reverse(
                    ListRolesView.urlname,
                    args=[self.domain]
                )

            elif (user.has_permission(self.domain, 'edit_locations')
                    or user.has_permission(self.domain, 'view_locations')):
                from corehq.apps.locations.views import LocationsListView
                redirect = reverse(
                    LocationsListView.urlname,
                    args=[self.domain]
                )

        return redirect

    def get(self, request, *args, **kwargs):
        if not self.redirect:
            raise Http404()
        return HttpResponseRedirect(self.redirect)


class BaseEditUserView(BaseUserSettingsView):

    @property
    @memoized
    def page_url(self):
        if self.urlname:
            return reverse(self.urlname, args=[self.domain, self.editable_user_id])

    @property
    def parent_pages(self):
        return [{
            'title': ListWebUsersView.page_title,
            'url': reverse(ListWebUsersView.urlname, args=[self.domain]),
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
            role = self.editable_user.get_role(self.domain)
        except DomainMembershipError:
            raise Http404()

        if role is None:
            if isinstance(self.editable_user, WebUser):
                raise ValueError("WebUser is always expected to have a role")
            return None
        else:
            return role.get_qualified_id()

    @property
    @memoized
    def editable_role_choices(self):
        return _get_editable_role_choices(self.domain, self.request.couch_user, allow_admin_role=False)

    @property
    def can_change_user_roles(self):
        return (
            bool(self.editable_role_choices) and
            self.request.couch_user.user_id != self.editable_user_id and
            (
                self.request.couch_user.is_domain_admin(self.domain) or
                not self.existing_role or
                self.existing_role in [choice[0] for choice in self.editable_role_choices]
            )
        )

    def form_user_update(self):
        raise NotImplementedError()

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
    def backup_token(self):
        if Domain.get_by_name(self.request.domain).two_factor_auth:
            device = self.editable_user.get_django_user().staticdevice_set.get_or_create(name='backup')[0]
            token = device.token_set.first()
            if token:
                return device.token_set.first().token
            else:
                return device.token_set.create(token=StaticToken.random_token()).token
        return None

    @property
    @memoized
    def commtrack_form(self):
        if self.request.method == "POST" and self.request.POST['form_type'] == "commtrack":
            return CommtrackUserForm(self.request.POST, domain=self.domain)

        user_domain_membership = self.editable_user.get_domain_membership(self.domain)
        return CommtrackUserForm(
            domain=self.domain,
            initial={
                'primary_location': user_domain_membership.location_id,
                'program_id': user_domain_membership.program_id,
                'assigned_locations': user_domain_membership.assigned_location_ids,
            },
        )

    def update_user(self):
        if self.form_user_update.is_valid():
            old_lang = self.request.couch_user.language
            if self.form_user_update.update_user():
                # if editing our own account we should also update the language in the session
                if self.editable_user._id == self.request.couch_user._id:
                    new_lang = self.request.couch_user.language
                    if new_lang != old_lang:
                        self.request.session['django_language'] = new_lang
                return True

    def post(self, request, *args, **kwargs):
        saved = False
        if self.request.POST['form_type'] == "commtrack":
            if self.commtrack_form.is_valid():
                self.commtrack_form.save(self.editable_user)
                saved = True
        elif self.request.POST['form_type'] == "update-user":
            if self.update_user():
                messages.success(self.request, _('Changes saved for user "%s"') % self.editable_user.raw_username)
                saved = True
        if saved:
            return HttpResponseRedirect(self.page_url)
        else:
            return self.get(request, *args, **kwargs)


@location_safe_for_ews_ils
class EditWebUserView(BaseEditUserView):
    template_name = "users/edit_web_user.html"
    urlname = "user_account"
    page_title = ugettext_noop("Edit Web User")

    @property
    def page_name(self):
        if self.request.is_view_only:
            return _("Edit Web User (View Only)")
        return self.page_title

    @property
    @memoized
    def form_user_update(self):
        if self.request.method == "POST" and self.request.POST['form_type'] == "update-user":
            data = self.request.POST
        else:
            data = None
        form = UpdateUserRoleForm(data=data, domain=self.domain, existing_user=self.editable_user)

        if self.can_change_user_roles:
            form.load_roles(current_role=self.existing_role, role_choices=self.user_role_choices)
        else:
            del form.fields['role']

        return form

    @property
    def user_role_choices(self):
        return _get_editable_role_choices(self.domain, self.request.couch_user, allow_admin_role=True)

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
    @memoized
    def can_grant_superuser_access(self):
        return self.request.couch_user.is_superuser and toggles.SUPPORT.enabled(self.request.couch_user.username)

    @property
    def page_context(self):
        ctx = {
            'form_uneditable': BaseUserInfoForm(),
            'can_edit_role': self.can_change_user_roles,
        }
        if self.request.is_view_only:
            make_form_readonly(self.commtrack_form)
        if (self.request.project.commtrack_enabled or
                self.request.project.uses_locations):
            ctx.update({'update_form': self.commtrack_form})
        if self.can_grant_superuser_access:
            ctx.update({'update_permissions': True})

        ctx.update({'token': self.backup_token})

        return ctx

    @method_decorator(require_can_edit_or_view_web_users)
    def dispatch(self, request, *args, **kwargs):
        return super(EditWebUserView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return super(EditWebUserView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self.request.is_view_only:
            return self.get(request, *args, **kwargs)

        if self.request.POST['form_type'] == "update-user-permissions" and self.can_grant_superuser_access:
            is_super_user = True if 'super_user' in self.request.POST and self.request.POST['super_user'] == 'on' else False
            if self.form_user_update_permissions.update_user_permission(couch_user=self.request.couch_user,
                                                                        editable_user=self.editable_user, is_super_user=is_super_user):
                messages.success(self.request, _('Changed system permissions for user "%s"') % self.editable_user.username)
        return super(EditWebUserView, self).post(request, *args, **kwargs)


def get_domain_languages(domain):
    query = (AppES()
             .domain(domain)
             .terms_aggregation('langs', 'languages')
             .size(0))
    app_languages = query.run().aggregations.languages.keys

    translation_doc = StandaloneTranslationDoc.get_obj(domain, 'sms')
    sms_languages = translation_doc.langs if translation_doc else []

    domain_languages = []
    for lang_code in set(app_languages + sms_languages):
        name = langcodes.get_name(lang_code)
        label = "{} ({})".format(lang_code, name) if name else lang_code
        domain_languages.append((lang_code, label))

    return sorted(domain_languages) or langcodes.get_all_langs_for_select()


@location_safe_for_ews_ils
class BaseRoleAccessView(BaseUserSettingsView):

    @property
    @memoized
    def can_restrict_access_by_location(self):
        return self.domain_object.has_privilege(
            privileges.RESTRICT_ACCESS_BY_LOCATION)

    @property
    @memoized
    def user_roles(self):
        user_roles = [AdminUserRole(domain=self.domain)]
        user_roles.extend(sorted(
            UserRole.by_domain(self.domain),
            key=lambda role: role.name if role.name else '\uFFFF'
        ))

        show_es_issue = False
        # skip the admin role since it's not editable
        for role in user_roles[1:]:
            try:
                role.hasUsersAssigned = bool(role.ids_of_assigned_users)
            except TypeError:
                # when query_result['hits'] returns None due to an ES issue
                show_es_issue = True
            role.has_unpermitted_location_restriction = (
                not self.can_restrict_access_by_location
                and not role.permissions.access_all_locations
            )
        if show_es_issue:
            messages.error(
                self.request,
                mark_safe(_(
                    "We might be experiencing issues fetching the entire list "
                    "of user roles right now. This issue is likely temporary and "
                    "nothing to worry about, but if you keep seeing this for "
                    "more than a day, please <a href='#modalReportIssue' "
                    "data-toggle='modal'>Report an Issue</a>."
                ))
            )
        return user_roles


class ListWebUsersView(BaseRoleAccessView):
    template_name = 'users/web_users.html'
    page_title = ugettext_lazy("Web Users")
    urlname = 'web_users'

    @method_decorator(require_can_edit_or_view_web_users)
    def dispatch(self, request, *args, **kwargs):
        return super(ListWebUsersView, self).dispatch(request, *args, **kwargs)

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
        invitations = Invitation.by_domain(self.domain)
        for invitation in invitations:
            invitation.role_label = self.role_labels.get(invitation.role, "")
        return invitations

    @property
    def page_context(self):
        return {
            'invitations': self.invitations,
            'requests': DomainRequest.by_domain(self.domain) if self.request.couch_user.is_domain_admin else [],
            'admins': WebUser.get_admins_by_domain(self.domain),
            'domain_object': self.domain_object,
        }


class ListRolesView(BaseRoleAccessView):
    template_name = 'users/roles_and_permissions.html'
    page_title = ugettext_lazy("Roles & Permissions")
    urlname = 'roles_and_permissions'

    @method_decorator(require_can_view_roles)
    def dispatch(self, request, *args, **kwargs):
        return super(ListRolesView, self).dispatch(request, *args, **kwargs)

    @property
    def can_edit_roles(self):
        return (has_privilege(self.request, privileges.ROLE_BASED_ACCESS)
                and self.couch_user.is_domain_admin)

    @property
    def is_location_safety_exempt(self):
        return toggles.LOCATION_SAFETY_EXEMPTION.enabled(self.domain)

    @property
    def landing_page_choices(self):
        return [
            {'id': None, 'name': _('Use Default')}
        ] + [
            {'id': page.id, 'name': _(page.name)}
            for page in get_allowed_landing_pages(self.domain)
        ]

    @property
    def page_context(self):
        if (not self.can_restrict_access_by_location
                and any(not role.permissions.access_all_locations
                        for role in self.user_roles)):
            messages.warning(self.request, _(
                "This project has user roles that restrict data access by "
                "organization, but the software plan no longer supports that. "
                "Any users assigned to roles that are restricted in data access "
                "by organization can no longer access this project.  Please "
                "update the existing roles."))
        return {
            'user_roles': self.user_roles,
            'can_edit_roles': self.can_edit_roles,
            'default_role': UserRole.get_default(),
            'report_list': get_possible_reports(self.domain),
            'web_apps_list': get_cloudcare_apps(self.domain),
            'apps_list': get_brief_apps_in_domain(self.domain),
            'is_domain_admin': self.couch_user.is_domain_admin,
            'domain_object': self.domain_object,
            'uses_locations': self.domain_object.uses_locations,
            'can_restrict_access_by_location': self.can_restrict_access_by_location,
            'is_location_safety_exempt': self.is_location_safety_exempt,
            'landing_page_choices': self.landing_page_choices,
            'show_integration': (
                toggles.OPENMRS_INTEGRATION.enabled(self.domain) or
                toggles.DHIS2_INTEGRATION.enabled(self.domain)
            ),
        }


@require_can_edit_or_view_web_users
@require_GET
@location_safe_for_ews_ils
def paginate_web_users(request, domain):
    def _query_es(limit, skip, query=None):
        web_user_filter = [
            {"term": {"user.domain_memberships.domain": domain}},
        ]
        web_user_filter.extend(ADD_TO_ES_FILTER['web_users'])

        q = {
            "filter": {"and": web_user_filter},
            "sort": {'username.exact': 'asc'},
        }
        default_fields = ["username", "last_name", "first_name"]
        q["query"] = search_string_query(query, default_fields)
        return es_query(
            params={}, q=q, es_index='users',
            size=limit, start_at=skip,
        )

    limit = int(request.GET.get('limit', 10))
    page = int(request.GET.get('page', 1))
    skip = limit * (page - 1)
    query = request.GET.get('query')

    web_users_query = _query_es(limit, skip, query=query)
    total = web_users_query.get('hits', {}).get('total', 0)
    results = web_users_query.get('hits', {}).get('hits', [])

    web_users = [WebUser.wrap(w['_source']) for w in results]

    def _fmt_result(domain, u):
        return {
            'email': u.get_email(),
            'domain': domain,
            'name': u.full_name,
            'role': u.role_label(domain),
            'phoneNumbers': u.phone_numbers,
            'id': u.get_id,
            'editUrl': reverse('user_account', args=[domain, u.get_id]),
            'removeUrl': (
                reverse('remove_web_user', args=[domain, u.user_id])
                if request.user.username != u.username else None
            ),
        }
    web_users_fmt = [_fmt_result(domain, u) for u in web_users]

    return json_response({
        'users': web_users_fmt,
        'total': total,
        'page': page,
        'query': query,
    })


@require_can_edit_web_users
@require_POST
@location_safe_for_ews_ils
def remove_web_user(request, domain, couch_user_id):
    user = WebUser.get_by_user_id(couch_user_id, domain)
    # if no user, very likely they just pressed delete twice in rapid succession so
    # don't bother doing anything.
    if user:
        record = user.delete_domain_membership(domain, create_record=True)
        user.save()
        if record:
            message = _('You have successfully removed {username} from your '
                        'project space. <a href="{url}" class="post-link">Undo</a>')
            messages.success(request, message.format(
                username=user.username,
                url=reverse('undo_remove_web_user', args=[domain, record.get_id])
            ), extra_tags="html")
        else:
            message = _('It appears {username} has already been removed from your project space.')
            messages.success(request, message.format(username=user.username))

    return HttpResponseRedirect(
        reverse(ListWebUsersView.urlname, args=[domain]))


@require_can_edit_web_users
@location_safe_for_ews_ils
def undo_remove_web_user(request, domain, record_id):
    record = DomainRemovalRecord.get(record_id)
    record.undo()
    messages.success(request, 'You have successfully restored {username}.'.format(
        username=WebUser.get_by_user_id(record.user_id).username
    ))

    return HttpResponseRedirect(
        reverse(ListWebUsersView.urlname, args=[domain]))


# If any permission less than domain admin were allowed here, having that permission would give you the permission
# to change the permissions of your own role such that you could do anything, and would thus be equivalent to having
# domain admin permissions.
@json_error
@domain_admin_required
@require_POST
def post_user_role(request, domain):
    if not domain_has_privilege(domain, privileges.ROLE_BASED_ACCESS):
        return json_response({})
    role_data = json.loads(request.body)
    role_data = dict(
        (p, role_data[p])
        for p in set(list(UserRole.properties()) + ['_id', '_rev']) if p in role_data
    )
    if (
        not domain_has_privilege(domain, privileges.RESTRICT_ACCESS_BY_LOCATION)
        and not role_data['permissions']['access_all_locations']
    ):
        # This shouldn't be possible through the UI, but as a safeguard...
        role_data['permissions']['access_all_locations'] = True

    role = UserRole.wrap(role_data)
    role.domain = domain
    if role.get_id:
        old_role = UserRole.get(role.get_id)
        assert(old_role.doc_type == UserRole.__name__)
        assert(old_role.domain == domain)

    if role.permissions.edit_web_users:
        role.permissions.view_web_users = True

    if role.permissions.edit_commcare_users:
        role.permissions.view_commcare_users = True

    if role.permissions.edit_groups:
        role.permissions.view_groups = True

    if role.permissions.edit_locations:
        role.permissions.view_locations = True

    if not role.permissions.edit_groups:
        role.permissions.edit_users_in_groups = False

    if not role.permissions.edit_locations:
        role.permissions.edit_users_in_locations = False

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


class UserInvitationView(object):
    # todo cleanup this view so it properly inherits from BaseSectionPageView
    template = "users/accept_invite.html"

    def __call__(self, request, invitation_id, **kwargs):
        logging.info("Don't use this view in more apps until it gets cleaned up.")
        # add the correct parameters to this instance
        self.request = request
        self.inv_id = invitation_id
        if 'domain' in kwargs:
            self.domain = kwargs['domain']

        if request.GET.get('switch') == 'true':
            logout(request)
            return redirect_to_login(request.path)
        if request.GET.get('create') == 'true':
            logout(request)
            return HttpResponseRedirect(request.path)

        try:
            invitation = Invitation.get(invitation_id)
        except ResourceNotFound:
            messages.error(request, _("Sorry, it looks like your invitation has expired. "
                                      "Please check the invitation link you received and try again, or request a "
                                      "project administrator to send you the invitation again."))
            return HttpResponseRedirect(reverse("login"))
        if invitation.is_accepted:
            messages.error(request, _("Sorry, that invitation has already been used up. "
                                      "If you feel this is a mistake please ask the inviter for "
                                      "another invitation."))
            return HttpResponseRedirect(reverse("login"))

        self.validate_invitation(invitation)

        if invitation.is_expired:
            return HttpResponseRedirect(reverse("no_permissions"))

        # Add zero-width space to username for better line breaking
        username = self.request.user.username.replace("@", "&#x200b;@")
        context = {
            'create_domain': False,
            'formatted_username': username,
            'domain': self.domain,
            'invite_to': self.domain,
            'invite_type': _('Project'),
            'hide_password_feedback': settings.ENABLE_DRACONIAN_SECURITY_FEATURES,
        }
        if request.user.is_authenticated:
            context['current_page'] = {'page_name': _('Project Invitation')}
        else:
            context['current_page'] = {'page_name': _('Project Invitation, Account Required')}
        if request.user.is_authenticated:
            is_invited_user = request.couch_user.username.lower() == invitation.email.lower()
            if self.is_invited(invitation, request.couch_user) and not request.couch_user.is_superuser:
                if is_invited_user:
                    # if this invite was actually for this user, just mark it accepted
                    messages.info(request, _("You are already a member of {entity}.").format(
                        entity=self.inviting_entity))
                    invitation.is_accepted = True
                    invitation.save()
                else:
                    messages.error(request, _("It looks like you are trying to accept an invitation for "
                                             "{invited} but you are already a member of {entity} with the "
                                             "account {current}. Please sign out to accept this invitation "
                                             "as another user.").format(
                                                 entity=self.inviting_entity,
                                                 invited=invitation.email,
                                                 current=request.couch_user.username,
                                             ))
                return HttpResponseRedirect(self.redirect_to_on_success)

            if not is_invited_user:
                messages.error(request, _("The invited user {invited} and your user {current} do not match!").format(
                    invited=invitation.email, current=request.couch_user.username))

            if request.method == "POST":
                couch_user = CouchUser.from_django_user(request.user, strict=True)
                self._invite(invitation, couch_user)
                track_workflow(request.couch_user.get_email(),
                               "Current user accepted a project invitation",
                               {"Current user accepted a project invitation": "yes"})
                send_hubspot_form(HUBSPOT_EXISTING_USER_INVITE_FORM, request)
                return HttpResponseRedirect(self.redirect_to_on_success)
            else:
                mobile_user = CouchUser.from_django_user(request.user).is_commcare_user()
                context.update({
                    'mobile_user': mobile_user,
                    "invited_user": invitation.email if request.couch_user.username != invitation.email else "",
                })
                return render(request, self.template, context)
        else:
            if request.method == "POST":
                form = WebUserInvitationForm(request.POST)
                if form.is_valid():
                    # create the new user
                    user = activate_new_user(form, domain=invitation.domain)
                    user.save()
                    messages.success(request, _("User account for %s created!") % form.cleaned_data["email"])
                    self._invite(invitation, user)
                    authenticated = authenticate(username=form.cleaned_data["email"],
                                                 password=form.cleaned_data["password"])
                    if authenticated is not None and authenticated.is_active:
                        login(request, authenticated)
                    track_workflow(request.POST['email'],
                                   "New User Accepted a project invitation",
                                   {"New User Accepted a project invitation": "yes"})
                    send_hubspot_form(HUBSPOT_NEW_USER_INVITE_FORM, request, user)
                    return HttpResponseRedirect(reverse("domain_homepage", args=[invitation.domain]))
            else:
                if CouchUser.get_by_username(invitation.email):
                    return HttpResponseRedirect(reverse("login") + '?next=' +
                        reverse('domain_accept_invitation', args=[invitation.domain, invitation.get_id]))
                form = WebUserInvitationForm(initial={
                    'email': invitation.email,
                    'hr_name': invitation.domain,
                    'create_domain': False,
                })

        context.update({"form": form})
        return render(request, self.template, context)

    def _invite(self, invitation, user):
        self.invite(invitation, user)
        invitation.is_accepted = True
        invitation.save()
        messages.success(self.request, self.success_msg)
        send_confirmation_email(invitation)

    def validate_invitation(self, invitation):
        assert invitation.domain == self.domain

    def is_invited(self, invitation, couch_user):
        return couch_user.is_member_of(invitation.domain)

    @property
    def inviting_entity(self):
        return self.domain

    @property
    def success_msg(self):
        return _('You have been added to the "%s" project space.') % self.domain

    @property
    def redirect_to_on_success(self):
        return reverse("domain_homepage", args=[self.domain,])

    def invite(self, invitation, user):
        user.add_as_web_user(invitation.domain, role=invitation.role,
                             location_id=invitation.supply_point, program_id=invitation.program)


@location_safe
@sensitive_post_parameters('password')
def accept_invitation(request, domain, invitation_id):
    return UserInvitationView()(request, invitation_id, domain=domain)


@require_POST
@require_can_edit_web_users
@location_safe_for_ews_ils
def reinvite_web_user(request, domain):
    invitation_id = request.POST['invite']
    try:
        invitation = Invitation.get(invitation_id)
        invitation.invited_on = datetime.utcnow()
        invitation.save()
        invitation.send_activation_email()
        return json_response({'response': _("Invitation resent"), 'status': 'ok'})
    except ResourceNotFound:
        return json_response({'response': _("Error while attempting resend"), 'status': 'error'})


@require_POST
@require_can_edit_web_users
@location_safe_for_ews_ils
def delete_invitation(request, domain):
    invitation_id = request.POST['id']
    invitation = Invitation.get(invitation_id)
    invitation.delete()
    return json_response({'status': 'ok'})


@require_POST
@require_can_edit_web_users
@location_safe_for_ews_ils
def delete_request(request, domain):
    DomainRequest.objects.get(id=request.POST['id']).delete()
    return json_response({'status': 'ok'})


class BaseManageWebUserView(BaseUserSettingsView):

    @method_decorator(require_can_edit_web_users)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseManageWebUserView, self).dispatch(request, *args, **kwargs)

    @property
    def parent_pages(self):
        return [{
            'title': ListWebUsersView.page_title,
            'url': reverse(ListWebUsersView.urlname, args=[self.domain]),
        }]


@location_safe_for_ews_ils
class InviteWebUserView(BaseManageWebUserView):
    template_name = "users/invite_web_user.html"
    urlname = 'invite_web_user'
    page_title = ugettext_lazy("Invite Web User to Project")

    @property
    @memoized
    def invite_web_user_form(self):
        role_choices = _get_editable_role_choices(self.domain, self.request.couch_user, allow_admin_role=True)
        loc = None
        domain_request = DomainRequest.objects.get(id=self.request_id) if self.request_id else None
        initial = {
            'email': domain_request.email if domain_request else None,
        }
        if 'location_id' in self.request.GET:
            from corehq.apps.locations.models import SQLLocation
            loc = SQLLocation.objects.get(location_id=self.request.GET.get('location_id'))
        if self.request.method == 'POST':
            current_users = [user.username for user in WebUser.by_domain(self.domain)]
            pending_invites = [di.email for di in Invitation.by_domain(self.domain)]
            return AdminInvitesUserForm(
                self.request.POST,
                excluded_emails=current_users + pending_invites,
                role_choices=role_choices,
                domain=self.domain
            )
        return AdminInvitesUserForm(initial=initial, role_choices=role_choices, domain=self.domain, location=loc)

    @property
    @memoized
    def request_id(self):
        if 'request_id' in self.request.GET:
            return self.request.GET.get('request_id')
        return None

    @property
    def page_context(self):
        return {
            'registration_form': self.invite_web_user_form,
            'request_id': self.request_id,
        }

    def post(self, request, *args, **kwargs):
        if self.invite_web_user_form.is_valid():
            # If user exists and has already requested access, just add them to the project
            # Otherwise, send an invitation
            create_invitation = True
            data = self.invite_web_user_form.cleaned_data
            domain_request = DomainRequest.by_email(self.domain, data["email"])
            if domain_request is not None:
                domain_request.is_approved = True
                domain_request.save()
                user = CouchUser.get_by_username(domain_request.email)
                if user is not None:
                    domain_request.send_approval_email()
                    create_invitation = False
                    user.add_as_web_user(self.domain, role=data["role"],
                                         location_id=data.get("supply_point", None),
                                         program_id=data.get("program", None))
                messages.success(request, "%s added." % data["email"])
            else:
                track_workflow(request.couch_user.get_email(),
                               "Sent a project invitation",
                               {"Sent a project invitation": "yes"})
                send_hubspot_form(HUBSPOT_INVITATION_SENT_FORM, request)
                messages.success(request, "Invitation sent to %s" % data["email"])

            if create_invitation:
                data["invited_by"] = request.couch_user.user_id
                data["invited_on"] = datetime.utcnow()
                data["domain"] = self.domain
                invite = Invitation(**data)
                invite.save()
                invite.send_activation_email()
            return HttpResponseRedirect(reverse(
                ListWebUsersView.urlname,
                args=[self.domain]
            ))
        return self.get(request, *args, **kwargs)


class DomainRequestView(BasePageView):
    urlname = "domain_request"
    page_title = ugettext_lazy("Request Access")
    template_name = "users/domain_request.html"
    request_form = None

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.request.domain])

    @property
    def page_context(self):
        domain_obj = Domain.get_by_name(self.request.domain)
        if self.request_form is None:
            initial = {'domain': domain_obj.name}
            if self.request.user.is_authenticated:
                initial.update({
                    'email': self.request.user.get_username(),
                    'full_name': self.request.user.get_full_name(),
                })
            self.request_form = DomainRequestForm(initial=initial)
        return {
            'domain': domain_obj.name,
            'hr_name': domain_obj.display_name(),
            'request_form': self.request_form,
        }

    def post(self, request, *args, **kwargs):
        self.request_form = DomainRequestForm(request.POST)
        if self.request_form.is_valid():
            data = self.request_form.cleaned_data
            with CriticalSection(["domain_request_%s" % data['domain']]):
                if DomainRequest.by_email(data['domain'], data['email']) is not None:
                    messages.error(request, _("A request is pending for this email. "
                        "You will receive an email when the request is approved."))
                else:
                    domain_request = DomainRequest(**data)
                    domain_request.send_request_email()
                    domain_request.save()
                    domain_obj = Domain.get_by_name(domain_request.domain)
                    return render(request, "users/confirmation_sent.html", {
                        'hr_name': domain_obj.display_name() if domain_obj else domain_request.domain,
                        'url': reverse("appstore"),
                    })
        return self.get(request, *args, **kwargs)


@require_POST
@require_permission_to_edit_user
@location_safe_for_ews_ils
def make_phone_number_default(request, domain, couch_user_id):
    user = CouchUser.get_by_user_id(couch_user_id, domain)
    if not user.is_current_web_user(request) and not user.is_commcare_user():
        raise Http404()

    phone_number = request.POST['phone_number']
    if not phone_number:
        raise Http404('Must include phone number in request.')

    user.set_default_phone_number(phone_number)
    from corehq.apps.users.views.mobile import EditCommCareUserView
    redirect = reverse(EditCommCareUserView.urlname, args=[domain, couch_user_id])
    return HttpResponseRedirect(redirect)


@require_POST
@require_permission_to_edit_user
@location_safe_for_ews_ils
def delete_phone_number(request, domain, couch_user_id):
    user = CouchUser.get_by_user_id(couch_user_id, domain)
    if not user.is_current_web_user(request) and not user.is_commcare_user():
        raise Http404()

    phone_number = request.POST['phone_number']
    if not phone_number:
        raise Http404('Must include phone number in request.')

    user.delete_phone_number(phone_number)
    from corehq.apps.users.views.mobile import EditCommCareUserView
    redirect = reverse(EditCommCareUserView.urlname, args=[domain, couch_user_id])
    return HttpResponseRedirect(redirect)


@require_permission_to_edit_user
@location_safe_for_ews_ils
def verify_phone_number(request, domain, couch_user_id):
    """
    phone_number cannot be passed in the url due to special characters
    but it can be passed as %-encoded GET parameters
    """
    if 'phone_number' not in request.GET:
        raise Http404('Must include phone number in request.')
    phone_number = six.moves.urllib.parse.unquote(request.GET['phone_number'])
    user = CouchUser.get_by_user_id(couch_user_id, domain)

    try:
        result = initiate_sms_verification_workflow(user, phone_number)
    except BadSMSConfigException as error:
        messages.error(request, _('Bad SMS configuration: {error}').format(error=error))
    else:
        if result == VERIFICATION__ALREADY_IN_USE:
            messages.error(request, _('Cannot start verification workflow. Phone number is already in use.'))
        elif result == VERIFICATION__ALREADY_VERIFIED:
            messages.error(request, _('Phone number is already verified.'))
        elif result == VERIFICATION__RESENT_PENDING:
            messages.success(request, _('Verification message resent.'))
        elif result == VERIFICATION__WORKFLOW_STARTED:
            messages.success(request, _('Verification workflow started.'))

    from corehq.apps.users.views.mobile import EditCommCareUserView
    redirect = reverse(EditCommCareUserView.urlname, args=[domain, couch_user_id])
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
@location_safe
def change_password(request, domain, login_id, template="users/partials/reset_password.html"):
    # copied from auth's password_change

    commcare_user = CommCareUser.get_by_user_id(login_id, domain)
    json_dump = {}
    if not commcare_user or not user_can_access_other_user(domain, request.couch_user, commcare_user):
        raise Http404()
    django_user = commcare_user.get_django_user()
    if request.method == "POST":
        form = SetUserPasswordForm(request.project, login_id, user=django_user, data=request.POST)
        if form.is_valid():
            form.save()
            json_dump['status'] = 'OK'
            form = SetUserPasswordForm(request.project, login_id, user='')
    else:
        form = SetUserPasswordForm(request.project, login_id, user=django_user)
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


@csrf_exempt
@require_POST
@require_superuser
def register_fcm_device_token(request, domain, couch_user_id, device_token):
    user = WebUser.get_by_user_id(couch_user_id)
    user.fcm_device_token = device_token
    user.save()
    return HttpResponse()


def _get_editable_role_choices(domain, couch_user, allow_admin_role):
    def role_to_choice(role):
        return (role.get_qualified_id(), role.name or _('(No Name)'))

    roles = UserRole.by_domain(domain)
    if not couch_user.is_domain_admin(domain):
        roles = [role for role in roles if role.is_non_admin_editable]
    elif allow_admin_role:
        roles = [AdminUserRole(domain=domain)] + roles
    return [role_to_choice(role) for role in roles]
