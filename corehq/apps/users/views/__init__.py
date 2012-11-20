from __future__ import absolute_import
from xml.sax.saxutils import escape
from functools import wraps
import json
from openpyxl.shared.exc import InvalidFileException
import re
import urllib
from datetime import datetime
import csv
import io
import logging
import calendar

from corehq.apps.registration.forms import NewWebUserRegistrationForm
from corehq.apps.registration.utils import activate_new_user
from dimagi.utils.couch.database import get_db
from django.contrib.auth import logout
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.auth.views import redirect_to_login
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.contrib import messages
from django_digest.decorators import httpdigest

from dimagi.utils.web import render_to_response, json_response, get_url_base, get_ip

from corehq.apps.registration.user_registration_backend.forms import AdminRegistersUserForm,\
    AdminInvitesUserForm
from corehq.apps.prescriptions.models import Prescription
from corehq.apps.sms.views import get_sms_autocomplete_context
from corehq.apps.domain.models import Domain
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.forms import UserForm, CommCareAccountForm, ProjectSettingsForm
from corehq.apps.users.models import CouchUser, Invitation, CommCareUser, WebUser, \
    RemoveWebUserRecord, UserRole, AdminUserRole
from corehq.apps.domain.decorators import login_and_domain_required, require_superuser, domain_admin_required
from corehq.apps.orgs.models import Team
from corehq.apps.reports.util import get_possible_reports
from corehq.apps.sms import verify as smsverify

require_can_edit_web_users = require_permission('edit_web_users')
require_can_edit_commcare_users = require_permission('edit_commcare_users')

def require_permission_to_edit_user(view_func):
    @wraps(view_func)
    def _inner(request, domain, couch_user_id, *args, **kwargs):
        go_ahead = False
        if hasattr(request, "couch_user"):
            user = request.couch_user
            if user.is_superuser or user.user_id == couch_user_id or (hasattr(user, "is_domain_admin") and user.is_domain_admin()):
                go_ahead = True
            else:
                couch_user = CouchUser.get_by_user_id(couch_user_id)
                if not couch_user:
                    raise Http404()
                if couch_user.is_commcare_user() and request.couch_user.can_edit_commcare_users():
                    go_ahead = True
                elif couch_user.is_web_user() and request.couch_user.can_edit_web_users():
                    go_ahead = True
        if go_ahead:
            return login_and_domain_required(view_func)(request, domain, couch_user_id, *args, **kwargs)
        else:
            raise Http404()
    return _inner

def _users_context(request, domain):
    couch_user = request.couch_user
    web_users = WebUser.by_domain(domain)
    teams = Team.get_by_domain(domain)
    for team in teams:
        for member_id in team.member_ids:
            team_user = WebUser.get(member_id)
            if team_user.get_id not in [web_user.get_id for web_user in web_users]:
                web_users.append(team_user)

    for user in [couch_user] + list(web_users):
        user.current_domain = domain

    return {
        'web_users': web_users,
        'domain': domain,
        'couch_user': couch_user,
    }

@login_and_domain_required
def users(request, domain):
    user = WebUser.get_by_user_id(request.couch_user._id, domain)
    if user:
        if user.has_permission(domain, 'edit_commcare_users'):
            redirect = reverse("commcare_users", args=[domain])
        else:
            redirect = reverse("user_account", args=[domain, request.couch_user._id])
    else:
        raise Http404()
    return HttpResponseRedirect(redirect)

@require_can_edit_web_users
def web_users(request, domain, template="users/web_users.html"):
    context = _users_context(request, domain)
    user_roles = [AdminUserRole(domain=domain)]
    user_roles.extend(sorted(UserRole.by_domain(domain), key=lambda role: role.name if role.name else u'\uFFFF'))

    role_labels = {}
    for r in user_roles:
        key = 'user-role:%s' % r.get_id if r.get_id else r.get_qualified_id()
        role_labels[key] = r.name

    invitations = Invitation.by_domain(domain)
    for invitation in invitations:
        invitation.role_label = role_labels.get(invitation.role, "")

    context.update({
        'user_roles': user_roles,
        'default_role': UserRole.get_default(),
        'report_list': get_possible_reports(domain),
        'invitations': invitations
    })
    return render_to_response(request, template, context)

@require_can_edit_web_users
@require_POST
def remove_web_user(request, domain, couch_user_id):
    user = WebUser.get_by_user_id(couch_user_id, domain)
    record = user.delete_domain_membership(domain, create_record=True)
    user.save()
    messages.success(request, 'You have successfully removed {username} from your domain. <a href="{url}" class="post-link">Undo</a>'.format(
        username=user.username,
        url=reverse('undo_remove_web_user', args=[domain, record.get_id])
    ), extra_tags="html")
    return HttpResponseRedirect(reverse('web_users', args=[domain]))

@require_can_edit_web_users
def undo_remove_web_user(request, domain, record_id):
    record = RemoveWebUserRecord.get(record_id)
    record.undo()
    messages.success(request, 'You have successfully restored {username}.'.format(
        username=WebUser.get_by_user_id(record.user_id).username
    ))
    return HttpResponseRedirect(reverse('web_users', args=[domain]))

# If any permission less than domain admin were allowed here, having that permission would give you the permission
# to change the permissions of your own role such that you could do anything, and would thus be equivalent to having
# domain admin permissions.
@domain_admin_required
@require_POST
def post_user_role(request, domain):
    role_data = json.loads(request.raw_post_data)
    role_data = dict([(p, role_data[p]) for p in set(UserRole.properties().keys() + ['_id', '_rev']) if p in role_data])
    role = UserRole.wrap(role_data)
    role.domain = domain
    if role.get_id:
        old_role = UserRole.get(role.get_id)
        assert(old_role.doc_type == UserRole.__name__)
    role.save()
    return json_response(role)

@transaction.commit_on_success
def accept_invitation(request, domain, invitation_id):
    if request.GET.get('switch') == 'true':
        logout(request)
        return redirect_to_login(request.path)
    if request.GET.get('create') == 'true':
        logout(request)
        return HttpResponseRedirect(request.path)
    invitation = Invitation.get(invitation_id)
    assert(invitation.domain == domain)
    if invitation.is_accepted:
        messages.error(request, "Sorry, that invitation has already been used up. "
                                "If you feel this is a mistake please ask the inviter for "
                                "another invitation.")
        return HttpResponseRedirect(reverse("login"))
    if request.user.is_authenticated():
        # if you are already authenticated, just add the domain to your
        # list of domains
        if request.couch_user.username != invitation.email:
            messages.error(request, "The invited user %s and your user %s do not match!" % (invitation.email, request.couch_user.username))

        if request.method == "POST":
            couch_user = CouchUser.from_django_user(request.user)
            couch_user.add_domain_membership(domain=domain)
            couch_user.set_role(domain, invitation.role)
            couch_user.save()
            invitation.is_accepted = True
            invitation.save()
            messages.success(request, "You have been added to the %s domain" % domain)
            return HttpResponseRedirect(reverse("domain_homepage", args=[domain,]))
        else:
            return render_to_response(request, 'users/accept_invite.html', {'domain': domain,
                                                                            "invited_user": invitation.email if request.couch_user.username != invitation.email else ""})
    else:
        # if you're not authenticated we need you to fill out your information
        if request.method == "POST":
            form = NewWebUserRegistrationForm(request.POST)
            if form.is_valid():
                user = activate_new_user(form, is_domain_admin=False, domain=invitation.domain)
                user.set_role(domain, invitation.role)
                user.save()
                invitation.is_accepted = True
                invitation.save()
                messages.success(request, "User account for %s created! You may now login." % form.cleaned_data["email"])
                return HttpResponseRedirect(reverse("login"))
        else:
            form = NewWebUserRegistrationForm(initial={'email': invitation.email})

        return render_to_response(request, "users/accept_invite.html", {"form": form})


@require_can_edit_web_users
def invite_web_user(request, domain, template="users/invite_web_user.html"):
    role_choices = UserRole.role_choices(domain)
    if request.method == "POST":
        form = AdminInvitesUserForm(request.POST,
            excluded_emails=[user.username for user in WebUser.by_domain(domain)],
            role_choices=role_choices
        )
        if form.is_valid():
            data = form.cleaned_data
            # create invitation record
            data["invited_by"] = request.couch_user.user_id
            data["invited_on"] = datetime.utcnow()
            data["domain"] = domain
            invite = Invitation(**data)
            invite.save()
            invite.send_activation_email()
            messages.success(request, "Invitation sent to %s" % invite.email)
            return HttpResponseRedirect(reverse("web_users", args=[domain]))
    else:
        form = AdminInvitesUserForm(role_choices=role_choices)
    context = _users_context(request, domain)
    context.update(
        registration_form=form
    )
    return render_to_response(request, template, context)

@require_permission_to_edit_user
def account(request, domain, couch_user_id, template="users/account.html"):
    context = _users_context(request, domain)
    couch_user = CouchUser.get_by_user_id(couch_user_id, domain)
    if not couch_user:
        raise Http404

    context.update({
        'couch_user': couch_user,
    })
    if couch_user.is_commcare_user():
        context.update({
            'reset_password_form': SetPasswordForm(user=""),
            'only_numeric': (request.project.password_format() == 'n'),
        })

    if couch_user.is_deleted():
        if couch_user.is_commcare_user():
            return render_to_response(request, 'users/deleted_account.html', context)
        else:
            raise Http404

    # phone-numbers tab
    if request.method == "POST" and request.POST['form_type'] == "phone-numbers":
        phone_number = request.POST['phone_number']
        if re.match(r'\d+', phone_number):
            couch_user.add_phone_number(phone_number)
            couch_user.save()
            #messages.success(request, 'Phone number added')
        else:
            messages.error(request, "Please enter digits only")

    # domain-accounts tab
    if not couch_user.is_commcare_user():
        all_domains = couch_user.get_domains()
        admin_domains = []
        for d in all_domains:
            if couch_user.is_domain_admin(d):
                admin_domains.append(d)
        context.update({"user": request.user,
                        "domains": admin_domains
        })
        # scheduled reports tab
    context.update({
        'phone_numbers_extended': couch_user.phone_numbers_extended(request.couch_user),

        # for commcare-accounts tab
        # "other_commcare_accounts": other_commcare_accounts,
    })

    #project settings tab
    if couch_user.user_id == request.couch_user.user_id and not couch_user.is_commcare_user():
        web_user = WebUser.get_by_user_id(couch_user.user_id)
        dm = web_user.get_domain_membership(domain)
        if dm:
            domain_obj = Domain.get_by_name(domain)
            if request.method == "POST" and request.POST['form_type'] == "project-settings":
                # deal with project settings data
                project_settings_form = ProjectSettingsForm(request.POST)
                if project_settings_form.is_valid():
                    if project_settings_form.save(web_user, domain):
                        messages.success(request, "Your project settings were successfully saved!")
                    else:
                        messages.error(request, "There seems to have been an error saving your project settings. Please try again!")
            else:
                project_settings_form = ProjectSettingsForm(initial={'global_timezone': domain_obj.default_timezone,
                                                                     'user_timezone': dm.timezone,
                                                                     'override_global_tz': dm.override_global_tz})
            context.update({
                'proj_settings_form': project_settings_form,
                'override_global_tz': dm.override_global_tz
            })

    # for basic tab
    context.update(_handle_user_form(request, domain, couch_user))
    return render_to_response(request, template, context)



@require_permission_to_edit_user
def delete_phone_number(request, domain, couch_user_id):
    """
    phone_number cannot be passed in the url due to special characters
    but it can be passed as %-encoded GET parameters
    """
    if 'phone_number' not in request.GET:
        return Http404('Must include phone number in request.')
    phone_number = urllib.unquote(request.GET['phone_number'])
    user = CouchUser.get_by_user_id(couch_user_id, domain)
    for i in range(0,len(user.phone_numbers)):
        if user.phone_numbers[i] == phone_number:
            del user.phone_numbers[i]
            break
    user.save()
    user.delete_verified_number(phone_number)
    return HttpResponseRedirect(reverse("user_account", args=(domain, couch_user_id )))

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

    # send verification message
    smsverify.send_verification(domain, user, phone_number)

    # create pending verified entry if doesn't exist already
    user.save_verified_number(domain, phone_number, False, None)

    return HttpResponseRedirect(reverse("user_account", args=(domain, couch_user_id )))


#@require_POST
#@require_permission_to_edit_user
#def link_commcare_account_to_user(request, domain, couch_user_id, commcare_login_id):
#    user = WebUser.get_by_user_id(couch_user_id, domain)
#    if 'commcare_couch_user_id' not in request.POST:
#        return Http404("Poorly formed link request")
#    user.link_commcare_account(domain,
#                               request.POST['commcare_couch_user_id'],
#                               commcare_login_id)
#    return HttpResponseRedirect(reverse("user_account", args=(domain, couch_user_id)))
#
#@require_POST
#@require_permission_to_edit_user
#def unlink_commcare_account(request, domain, couch_user_id, commcare_user_index):
#    user = WebUser.get_by_user_id(couch_user_id, domain)
#    if commcare_user_index:
#        user.unlink_commcare_account(domain, commcare_user_index)
#        user.save()
#    return HttpResponseRedirect(reverse("user_account", args=(domain, couch_user_id )))

#@login_and_domain_required
#def my_domains(request, domain):
#    return HttpResponseRedirect(reverse("domain_accounts", args=(domain, request.couch_user._id)))

@require_superuser
@login_and_domain_required
def domain_accounts(request, domain, couch_user_id, template="users/domain_accounts.html"):
    context = _users_context(request, domain)
    couch_user = WebUser.get_by_user_id(couch_user_id, domain)
    if request.method == "POST" and 'domain' in request.POST:
        domain = request.POST['domain']
        couch_user.add_domain_membership(domain)
        couch_user.save()
        messages.success(request,'Domain added')
    context.update({"user": request.user})
    return render_to_response(request, template, context)

@require_POST
@require_superuser
def add_domain_membership(request, domain, couch_user_id, domain_name):
    user = WebUser.get_by_user_id(couch_user_id, domain)
    if domain_name:
        user.add_domain_membership(domain_name)
        user.save()
    return HttpResponseRedirect(reverse("user_account", args=(domain, couch_user_id)))

@require_POST
@require_superuser
def delete_domain_membership(request, domain, couch_user_id, domain_name):
    user = WebUser.get_by_user_id(couch_user_id, domain)
    user.delete_domain_membership(domain_name)
    user.save()
    return HttpResponseRedirect(reverse("user_account", args=(domain, couch_user_id )))

@login_and_domain_required
def change_password(request, domain, login_id, template="users/partial/reset_password.html"):
    # copied from auth's password_change

    commcare_user = CommCareUser.get_by_user_id(login_id, domain)
    json_dump = {}
    if not commcare_user:
        raise Http404
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


# this view can only change the current user's password
@login_and_domain_required
def change_my_password(request, domain, template="users/change_my_password.html"):
    # copied from auth's password_change
    if request.method == "POST":
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Your password was successfully changed!")
            return HttpResponseRedirect(reverse('user_account', args=[domain, request.couch_user._id]))
    else:
        form = PasswordChangeForm(user=request.user)
    context = _users_context(request, domain)
    context.update({
        'form': form,
    })
    return render_to_response(request, template, context)


def _handle_user_form(request, domain, couch_user=None):
    from corehq.apps.reports.util import get_possible_reports
    context = {}
    if couch_user:
        create_user = False
    else:
        create_user = True
    can_change_admin_status = ((request.user.is_superuser or request.couch_user.can_edit_web_users(domain=domain))
        and request.couch_user.user_id != couch_user.user_id)

    if couch_user.is_commcare_user():
        role_choices = UserRole.commcareuser_role_choices(domain)
    else:
        role_choices = UserRole.role_choices(domain)

    if request.method == "POST" and request.POST['form_type'] == "basic-info":
        form = UserForm(request.POST, role_choices=role_choices)
        if form.is_valid():
            if create_user:
                django_user = User()
                django_user.username = form.cleaned_data['email']
                django_user.save()
                couch_user = CouchUser.from_django_user(django_user)
            couch_user.first_name = form.cleaned_data['first_name']
            couch_user.last_name = form.cleaned_data['last_name']
            couch_user.email = form.cleaned_data['email']
            couch_user.language = form.cleaned_data['language']
            if can_change_admin_status:
                role = form.cleaned_data['role']
                if role:
                    couch_user.set_role(domain, role)
            couch_user.save()
            if request.couch_user.get_id == couch_user.get_id and couch_user.language:
                # update local language in the session
                request.session['django_language'] = couch_user.language

            messages.success(request, 'Changes saved for user "%s"' % couch_user.username)
    else:
        form = UserForm(role_choices=role_choices)
        if not create_user:
            form.initial['first_name'] = couch_user.first_name
            form.initial['last_name'] = couch_user.last_name
            form.initial['email'] = couch_user.email
            form.initial['language'] = couch_user.language
            if can_change_admin_status:
                if couch_user.is_commcare_user():
                    role = couch_user.get_role(domain)
                    if role is None:
                        initial = "none"
                    else:
                        initial = role.get_qualified_id()
                    form.initial['role'] = initial
                else:
                    form.initial['role'] = couch_user.get_role(domain).get_qualified_id() or ''

    if not can_change_admin_status:
        del form.fields['role']

    context.update({"form": form})
    return context

@httpdigest
@login_and_domain_required
def test_httpdigest(request, domain):
    return HttpResponse("ok")



@login_and_domain_required
def test_autocomplete(request, domain, template="users/test_autocomplete.html"):
    context = _users_context(request, domain)
    context.update(get_sms_autocomplete_context(request, domain))
    return render_to_response(request, template, context)

@Prescription.require('user-domain-transfer')
@login_and_domain_required
def user_domain_transfer(request, domain, prescription, template="users/domain_transfer.html"):
    target_domain = prescription.params['target_domain']
    if not request.couch_user.is_domain_admin(target_domain):
        return HttpResponseForbidden()
    if request.method == "POST":
        user_ids = request.POST.getlist('user_id')
        app_id = request.POST['app_id']
        errors = []
        for user_id in user_ids:
            user = CommCareUser.get_by_user_id(user_id, domain)
            try:
                user.transfer_to_domain(target_domain, app_id)
            except Exception as e:
                errors.append((user_id, user, e))
            else:
                messages.success(request, "Successfully transferred {user.username}".format(user=user))
        if errors:
            messages.error(request, "Failed to transfer the following users")
            for user_id, user, e in errors:
                if user:
                    messages.error(request, "{user.username} ({user.user_id}): {e}".format(user=user, e=e))
                else:
                    messages.error(request, "CommCareUser {user_id} not found".format(user_id=user_id))
        return HttpResponseRedirect(reverse('commcare_users', args=[target_domain]))
    else:
        from corehq.apps.app_manager.models import VersionedDoc
        # apps from the *target* domain
        apps = VersionedDoc.view('app_manager/applications_brief', startkey=[target_domain], endkey=[target_domain, {}])
        # useres from the *originating* domain
        users = list(CommCareUser.by_domain(domain))
        users.extend(CommCareUser.by_domain(domain, is_active=False))
        context = _users_context(request, domain)
        context.update({
            'apps': apps,
            'commcare_users': users,
            'target_domain': target_domain
        })
        return render_to_response(request, template, context)

@require_superuser
def audit_logs(request, domain):
    from auditcare.models import NavigationEventAudit
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

def eula_agreement(request, domain):
    domain = Domain.get_by_name(domain)
    if request.method == 'POST':
        current_user = CouchUser.from_django_user(request.user)
        current_user.eula.signed = True
        current_user.eula.date = datetime.utcnow()
        current_user.eula.type = 'End User License Agreement'
        current_user.eula.user_ip = get_ip(request)
        current_user.save()

    return HttpResponseRedirect(reverse("corehq.apps.reports.views.default", args=[domain]))
