import json
import re
from smtplib import SMTPRecipientsRefused
import urllib
from datetime import datetime
from django.contrib.auth import logout
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from corehq.apps.domain.user_registration_backend import register_user
from corehq.apps.domain.user_registration_backend.forms import AdminRegistersUserForm,\
    AdminInvitesUserForm, UserRegistersSelfForm
from corehq.apps.prescriptions.models import Prescription
from corehq.apps.sms.views import get_sms_autocomplete_context
from corehq.apps.domain.models import Domain
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.forms import UserForm, CommCareAccountForm
from corehq.apps.users.models import CouchUser, Invitation, CommCareUser, WebUser, RemoveWebUserRecord
from corehq.apps.groups.models import Group
from corehq.apps.domain.decorators import login_and_domain_required, require_superuser
from dimagi.utils.web import render_to_response, json_response
import calendar
from corehq.apps.reports.schedule.config import ScheduledReportFactory
from corehq.apps.reports.models import WeeklyReportNotification, DailyReportNotification, ReportNotification
from django.contrib import messages
from corehq.apps.reports.tasks import send_report
from django_digest.decorators import httpdigest


def require_permission_to_edit_user(view_func):
    def _inner(request, domain, couch_user_id, *args, **kwargs):
        if hasattr(request, "couch_user") and (request.user.is_superuser or request.couch_user.can_edit_users(domain) or request.couch_user._id == couch_user_id):
            return login_and_domain_required(view_func)(request, domain, couch_user_id, *args, **kwargs)
        else:
            raise Http404()
    return _inner

require_can_edit_users = require_permission('edit-users')

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

@login_and_domain_required
def users(request, domain):
    return HttpResponseRedirect(reverse(
        "user_account",
        args=[domain, request.couch_user._id],
    ))

@require_can_edit_users
def web_users(request, domain, template="users/web_users.html"):
    context = _users_context(request, domain)
    return render_to_response(request, template, context)

@require_can_edit_users
@transaction.commit_on_success
def create_web_user(request, domain, template="users/create_web_user.html"):
    if request.method == "POST":
        form = AdminRegistersUserForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            assert(data['password_1'] == data['password_2'])
            data['password'] = data['password_1']
            del data['password_1']
            del data['password_2']
            new_user = register_user(domain, send_email=True, **data)
            return HttpResponseRedirect(reverse("web_users", args=[domain]))
    else:
        form = AdminRegistersUserForm()
    context = _users_context(request, domain)
    context.update(
        registration_form=form
    )
    return render_to_response(request, template, context)

@require_can_edit_users
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

@require_can_edit_users
def undo_remove_web_user(request, domain, record_id):
    record = RemoveWebUserRecord.get(record_id)
    record.undo()
    messages.success(request, 'You have successfully restored {username}.'.format(
        username=WebUser.get_by_user_id(record.user_id).username
    ))
    return HttpResponseRedirect(reverse('web_users', args=[domain]))

@transaction.commit_on_success
def accept_invitation(request, domain, invitation_id):
    invitation = Invitation.get(invitation_id)
    assert(invitation.domain == domain)
    if invitation.is_accepted:
        messages.error(request, "Sorry that invitation has already been used up. "
                       "If you feel this is a mistake please ask the inviter for "
                       "another invitation.")
        return HttpResponseRedirect(reverse("homepage"))
    if request.user.is_authenticated():
        # if you are already authenticated, just add the domain to your 
        # list of domains
        if request.user.username == invitation.email:
            couch_user = CouchUser.from_django_user(request.user)
            couch_user.add_domain_membership(domain=domain, is_admin=invitation.is_domain_admin)
            couch_user.save()
            invitation.is_accepted = True
            invitation.save()
            messages.success(request, "You have been added to the %s domain" % domain)
            return HttpResponseRedirect(reverse("domain_homepage", args=[domain,]))
        else:
            logout(request)
    if not request.user.is_authenticated():
        # if you're not authenticated we need you to fill out your information
        if request.method == "POST":
            form = UserRegistersSelfForm(request.POST)
            if form.is_valid():
                data = form.cleaned_data
                assert(data['password_1'] == data['password_2'])
                data['password'] = data['password_1']
                del data['password_1']
                del data['password_2']
                del data["tos_confirmed"]  
                user = register_user(invitation.domain, send_email=False, 
                                     is_domain_admin=invitation.is_domain_admin, **data)
                invitation.is_accepted = True
                invitation.save()
                messages.success(request, "User account for %s created! You may now login." % data["email"])
                return HttpResponseRedirect(reverse("login"))
        else:
            user = WebUser.get_by_username(invitation.email)
            if user:
                return HttpResponseRedirect(reverse('login') + '?next=%s' % urllib.quote(request.path))
            else:
                form = UserRegistersSelfForm(initial={'email': invitation.email})
        
        return render_to_response(request, "users/accept_invite.html", {"form": form})


@require_can_edit_users
def invite_web_user(request, domain, template="users/invite_web_user.html"):
    if request.method == "POST":
        form = AdminInvitesUserForm(request.POST)
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
        form = AdminInvitesUserForm()
    context = _users_context(request, domain)
    context.update(
        registration_form=form
    )
    return render_to_response(request, template, context)

@require_can_edit_users
def commcare_users(request, domain, template="users/commcare_users.html"):
    show_inactive = json.loads(request.GET.get('show_inactive', 'false'))
    context = _users_context(request, domain)
    users = CommCareUser.by_domain(domain)
    if show_inactive:
        users = list(users)
        users.extend(CommCareUser.by_domain(domain, is_active=False))
    context.update({
        'commcare_users': users,
        'show_inactive': show_inactive
    })
    return render_to_response(request, template, context)

@require_can_edit_users
def archive_commcare_user(request, domain, user_id, is_active=False):
    user = CommCareUser.get_by_user_id(user_id, domain)
    user.is_active = is_active
    user.save()
    return HttpResponseRedirect(reverse('commcare_users', args=[domain]))

@require_can_edit_users
@require_POST
def delete_commcare_user(request, domain, user_id):
    user = CommCareUser.get_by_user_id(user_id, domain)
    user.retire()
    messages.success(request, "User %s and all their submissions have been permanently deleted" % user.username)
    return HttpResponseRedirect(reverse('commcare_users', args=[domain]))


@require_permission_to_edit_user
def account(request, domain, couch_user_id, template="users/account.html"):
    context = _users_context(request, domain)
    couch_user = CouchUser.get_by_user_id(couch_user_id, domain)

    if not couch_user:
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
    if request.user.is_superuser and not couch_user.is_commcare_user():
        my_domains = couch_user.get_domains()
        context.update({"user": request.user,
                        "domains": my_domains
                        })
    # scheduled reports tab
    context.update({
        'couch_user': couch_user,
        # for phone-number tab
        'phone_numbers': couch_user.phone_numbers,

        # for commcare-accounts tab
#        "other_commcare_accounts": other_commcare_accounts,
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
    my_domains = couch_user.get_domains()
    context['other_domains'] = [d.name for d in Domain.objects.exclude(name__in=my_domains)]
    context.update({"user": request.user,
                    "domains": couch_user.get_domains(),
                    })
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
    if not commcare_user:
        raise Http404
    django_user = commcare_user.get_django_user()
    if request.method == "POST":
        form = SetPasswordForm(user=django_user, data=request.POST)
        if form.is_valid():
            form.save()
            return HttpResponse(json.dumps({'status': 'ok'}))
    else:
        form = SetPasswordForm(user=django_user)
    context = _users_context(request, domain)
    context.update({
        'form': form,
    })
    return HttpResponse(json.dumps({'formHTML': render_to_string(template, context)}))


# this view can only change the current user's password
@login_and_domain_required
def change_my_password(request, domain, template="users/change_my_password.html"):
    # copied from auth's password_change
    if request.method == "POST":
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('user_account', args=[domain, request.couch_user._id]))
    else:
        form = PasswordChangeForm(user=request.user)
    context = _users_context(request, domain)
    context.update({
        'form': form,
    })
    return render_to_response(request, template, context)



def _handle_user_form(request, domain, couch_user=None):
    context = {}
    if couch_user:
        create_user = False
    else:
        create_user = True
    can_change_admin_status = \
        (request.user.is_superuser or request.couch_user.can_edit_users(domain))\
        and request.couch_user.user_id != couch_user.user_id and not couch_user.is_commcare_user()
    if request.method == "POST" and request.POST['form_type'] == "basic-info":
        form = UserForm(request.POST)
        if form.is_valid():
            if create_user:
                django_user = User()
                django_user.username = form.cleaned_data['email']
                django_user.save()
                couch_user = CouchUser.from_django_user(django_user)
            couch_user.first_name = form.cleaned_data['first_name']
            couch_user.last_name = form.cleaned_data['last_name']
            couch_user.email = form.cleaned_data['email']
            if can_change_admin_status:
                role = form.cleaned_data['role']
                couch_user.set_role(domain, role)
            couch_user.save()
            messages.success(request, 'Changes saved for user "%s"' % couch_user.username)
    else:
        form = UserForm()
        if not create_user:
            form.initial['first_name'] = couch_user.first_name
            form.initial['last_name'] = couch_user.last_name
            form.initial['email'] = couch_user.email
            if can_change_admin_status:
                form.initial['role'] = couch_user.get_role(domain)

    if not can_change_admin_status:
        del form.fields['role']

    context.update({"form": form})
    return context

@httpdigest
@login_and_domain_required
def test_httpdigest(request, domain):
    return HttpResponse("ok")

@login_and_domain_required
def add_scheduled_report(request, domain, couch_user_id):
    if request.method == "POST":
        report_type = request.POST["report_type"]
        hour = request.POST["hour"]
        day = request.POST["day"]
        if day=="all":
            report = DailyReportNotification()
        else:
            report = WeeklyReportNotification()
            report.day_of_week = int(day)
        report.hours = int(hour)
        report.domain = domain
        report.report_slug = report_type
        report.user_ids = [couch_user_id]
        report.save()
        messages.success(request, "New scheduled report added!")
        return HttpResponseRedirect(reverse("user_account", args=(domain, couch_user_id )))
    
    context = _users_context(request, domain)
    context.update({"hours": [(val, "%s:00" % val) for val in range(24)],
                    "days":  [(val, calendar.day_name[val]) for val in range(7)],
                    "reports": dict([(key, value) for (key, value) in  ScheduledReportFactory.get_reports().items() if value.auth(request.user)])})
    return render_to_response(request, "users/add_scheduled_report.html", context)

@login_and_domain_required
@require_POST
def drop_scheduled_report(request, domain, couch_user_id, report_id):
    rep = ReportNotification.get(report_id)
    try:
        rep.user_ids.remove(couch_user_id)
    except ValueError:
        pass # odd, the user wasn't there in the first place
    if len(rep.user_ids) == 0:
        rep.delete()
    else:
        rep.save()
    messages.success(request, "Scheduled report dropped!")
    return HttpResponseRedirect(reverse("user_account", args=(domain, couch_user_id )))

@login_and_domain_required
@require_POST
def test_scheduled_report(request, domain, couch_user_id, report_id):
    rep = ReportNotification.get(report_id)
    user = WebUser.get_by_user_id(couch_user_id, domain)
    try:
        send_report(rep, user)
    except SMTPRecipientsRefused:
        messages.error(request, "You have no email address configured")
    else:
        messages.success(request, "Test message sent to %s" % user.get_email())

    return HttpResponseRedirect(reverse("user_account", args=(domain, couch_user_id )))

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
GROUP VIEWS
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""


def _get_groups(domain):
    key = [domain]
    groups = Group.view("groups/by_name", startkey=key, endkey=key + [{}], include_docs=True)
    for group in groups:
        name = group.name if group.name else '-'
        if group.name != name:
            group.name = name
            group.save()
    return groups


@require_can_edit_users
def all_groups(request, domain, template="groups/all_groups.html"):
    context = _users_context(request, domain)
    all_groups = _get_groups(domain)
    context.update({
        'domain': domain,
        'all_groups': all_groups
    })
    return render_to_response(request, template, context)

@require_can_edit_users
def group_members(request, domain, group_id, template="groups/group_members.html"):
    context = _users_context(request, domain)
    all_groups = _get_groups(domain)
    group = Group.get(group_id)
    if group is None:
        raise Http404("Group %s does not exist" % group_id)
    member_ids = group.get_user_ids()
    members = CouchUser.view("_all_docs", keys=member_ids, include_docs=True).all()
    members.sort(key=lambda user: user.username)
    all_users = CommCareUser.by_domain(domain)
    member_ids = set(member_ids)
    nonmembers = [user for user in all_users if user.user_id not in member_ids]

    context.update({"domain": domain,
                    "group": group,
                    "all_groups": all_groups,
                    "members": members,
                    "nonmembers": nonmembers,
                    })
    return render_to_response(request, template, context)

#@require_domain_admin
#def my_groups(request, domain, template="groups/groups.html"):
#    return group_membership(request, domain, request.couch_user._id, template)

@require_can_edit_users
def group_membership(request, domain, couch_user_id, template="groups/groups.html"):
    context = _users_context(request, domain)
    couch_user = CouchUser.get_by_user_id(couch_user_id, domain)
    if request.method == "POST" and 'group' in request.POST:
        group = request.POST['group']
        group.add_user(couch_user)
        group.save()
        #messages.success(request, '%s joined group %s' % (couch_user.username, group.name))
    my_groups = Group.view("groups/by_user", key=couch_user_id, include_docs=True).all()
    all_groups = Group.view("groups/by_domain", key=domain, include_docs=True).all()
    other_groups = []
    for group in all_groups:
        if group.get_id not in [g.get_id for g in my_groups]:
            other_groups.append(group)
    #other_groups = [group for group in all_groups if group not in my_groups]
    context.update({"domain": domain,
                    "groups": my_groups, 
                    "other_groups": other_groups,
                    "couch_user":couch_user })
    return render_to_response(request, template, context)

@require_can_edit_users
def add_commcare_account(request, domain, template="users/add_commcare_account.html"):
    """
    Create a new commcare account
    """
    context = _users_context(request, domain)
    if request.method == "POST":
        form = CommCareAccountForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]

            couch_user = CommCareUser.create(domain, username, password, device_id='Generated from HQ')
            couch_user.save()
            return HttpResponseRedirect(reverse("commcare_users", args=[domain]))
    else:
        form = CommCareAccountForm()
    context.update(form=form)
    return render_to_response(request, template, context)

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
