import logging
import re

from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.views.generic.base import TemplateView, View

from memoized import memoized

from corehq.apps.sso.models import IdentityProvider
from dimagi.utils.couch import CriticalSection
from dimagi.utils.couch.resource_conflict import retry_resource
from dimagi.utils.web import get_ip

from corehq.apps.accounting.models import BillingAccount
from corehq.apps.analytics import ab_tests
from corehq.apps.analytics.tasks import (
    HUBSPOT_COOKIE,
    track_clicked_signup_on_hubspot,
    track_confirmed_account_on_hubspot,
    track_web_user_registration_hubspot,
    track_workflow,
)
from corehq.apps.analytics.utils import get_meta
from corehq.apps.domain.decorators import login_required
from corehq.apps.domain.exceptions import NameUnavailableException, ErrorInitializingDomain
from corehq.apps.domain.extension_points import has_custom_clean_password
from corehq.apps.domain.models import Domain, LicenseAgreement
from corehq.apps.hqwebapp.decorators import use_jquery_ui, use_ko_validation
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.registration.forms import (
    DomainRegistrationForm,
    RegisterWebUserForm,
)
from corehq.apps.registration.models import (
    RegistrationRequest,
    AsyncSignupRequest,
)
from corehq.apps.registration.utils import (
    activate_new_user_via_reg_form,
    project_logo_emails_context,
    request_new_domain,
    send_domain_registration_email,
    send_mobile_experience_reminder,
    send_new_request_update_email,
)
from corehq.apps.users.models import CouchUser, WebUser, Invitation, EULA_CURRENT_VERSION
from corehq.const import USER_CHANGE_VIA_WEB
from corehq.util.context_processors import get_per_domain_context
from corehq.util.jqueryrmi import JSONResponseMixin, allow_remote_invocation
from corehq.util.soft_assert import soft_assert

_domainless_new_user_soft_assert = soft_assert(to=[
    '{}@{}'.format('biyeun', 'dimagi.com')
], send_to_ops=False, fail_if_debug=False)


CONFIRMATION_RESEND_LIMIT_SECONDS = 60


def get_domain_context():
    return get_per_domain_context(Domain())


def registration_default(request):
    return redirect(UserRegistrationView.urlname)


class ProcessRegistrationView(JSONResponseMixin, View):
    urlname = 'process_registration'

    def get(self, request, *args, **kwargs):
        raise Http404()

    def _create_new_account(self, reg_form, additional_hubspot_data=None):
        activate_new_user_via_reg_form(
            reg_form,
            created_by=None,
            created_via=USER_CHANGE_VIA_WEB,
            ip=get_ip(self.request)
        )
        new_user = authenticate(
            username=reg_form.cleaned_data['email'],
            password=reg_form.cleaned_data['password'],
            request=self.request
        )
        web_user = WebUser.get_by_username(new_user.username, strict=True)

        if 'phone_number' in reg_form.cleaned_data and reg_form.cleaned_data['phone_number']:
            web_user.phone_numbers.append(reg_form.cleaned_data['phone_number'])
            web_user.save()

        if settings.IS_SAAS_ENVIRONMENT:
            email = new_user.email

            # registration analytics
            # only do anything with this in a SAAS environment

            persona = reg_form.cleaned_data['persona']
            persona_other = reg_form.cleaned_data['persona_other']

            track_workflow(email, "Requested New Account", {
                'environment': settings.SERVER_ENVIRONMENT,
            })
            track_workflow(email, "Persona Field Filled Out", {
                'personachoice': persona,
                'personaother': persona_other,
            })

            if not additional_hubspot_data:
                additional_hubspot_data = {}
            additional_hubspot_data.update({
                'buyer_persona': persona,
                'buyer_persona_other': persona_other,
            })
            track_web_user_registration_hubspot(
                self.request,
                web_user,
                additional_hubspot_data
            )
            if not persona or (persona == 'Other' and not persona_other):
                # There shouldn't be many instances of this.
                _assert = soft_assert('@'.join(['bbuczyk', 'dimagi.com']), exponential_backoff=False)
                _assert(
                    False,
                    "[BAD PERSONA DATA] Persona fields during "
                    "login submitted empty. User: {}".format(email)
                )

        login(self.request, new_user)

    @allow_remote_invocation
    def register_new_user(self, data):
        idp = None
        if settings.ENFORCE_SSO_LOGIN:
            idp = IdentityProvider.get_required_identity_provider(data['data']['email'])

        reg_form = RegisterWebUserForm(data['data'], is_sso=idp is not None)
        if reg_form.is_valid():
            ab_test = ab_tests.SessionAbTest(ab_tests.APPCUES_V3_APP, self.request)
            appcues_ab_test = ab_test.context['version']

            if idp:
                signup_request = AsyncSignupRequest.create_from_registration_form(
                    reg_form,
                    additional_hubspot_data={
                        "appcues_test": appcues_ab_test,
                    }
                )
                return {
                    'success': True,
                    'appcues_ab_test': appcues_ab_test,
                    'ssoLoginUrl': idp.get_login_url(signup_request.username),
                    'ssoIdpName': idp.name,
                }

            self._create_new_account(reg_form, additional_hubspot_data={
                "appcues_test": appcues_ab_test,
            })
            try:
                request_new_domain(
                    self.request,
                    reg_form.cleaned_data['project_name'],
                    is_new_user=True
                )
            except NameUnavailableException:
                # technically, the form should never reach this as names are
                # auto-generated now. But, just in case...
                logging.error("There as an issue generating a unique domain name "
                              "for a user during new registration.")
                return {
                    'errors': {
                        'project name unavailable': [],
                    }
                }
            except ErrorInitializingDomain as e:
                logging.error(f"Unable to initialize domain during new user signup: {str(e)}")
                return {
                    'errors': {
                        'temporary system issue': [],
                    }
                }
            return {
                'success': True,
                'appcues_ab_test': appcues_ab_test,
            }
        logging.error(
            "There was an error processing a new user registration form."
            "This shouldn't happen as validation should be top-notch "
            "client-side. Here is what the errors are: {}".format(reg_form.errors))
        return {
            'errors': reg_form.errors,
        }

    @allow_remote_invocation
    def check_username_availability(self, data):
        email = data['email'].strip()
        duplicate = CouchUser.get_by_username(email)
        is_existing = User.objects.filter(username__iexact=email).count() > 0 or duplicate

        message = None
        restricted_by_domain = None
        if is_existing:
            message = _("There is already a user with this email.")
        else:
            domain = email[email.find("@") + 1:]
            for account in BillingAccount.get_enterprise_restricted_signup_accounts():
                if domain in account.enterprise_restricted_signup_domains:
                    restricted_by_domain = domain
                    message = account.restrict_signup_message
                    regex = r'(\b[a-zA-Z0-9_.+%-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b)'
                    subject = _("CommCareHQ account request")
                    message = re.sub(regex, "<a href='mailto:\\1?subject={}'>\\1</a>".format(subject), message)
                    break

        response = {
            'isValid': message is None,
            'restrictedByDomain': restricted_by_domain,
            'message': message,
        }
        if settings.ENFORCE_SSO_LOGIN and response['isValid']:
            idp = IdentityProvider.get_required_identity_provider(email)
            if idp:
                response.update({
                    'isSso': True,
                    'ssoMessage': _(
                        "This email is managed by {}. You will be asked to login "
                        "with Single Sign-On after the next step."
                    ).format(idp.name),
                })
        return response


class UserRegistrationView(BasePageView):
    urlname = 'register_user'
    template_name = 'registration/register_new_user.html'

    @use_jquery_ui
    @use_ko_validation
    @method_decorator(transaction.atomic)
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            # Redirect to a page which lets user choose whether or not to create a new account
            domains_for_user = Domain.active_for_user(request.user)
            if len(domains_for_user) == 0:
                return redirect("registration_domain")
            else:
                return redirect("homepage")
        response = super(UserRegistrationView, self).dispatch(request, *args, **kwargs)
        if settings.IS_SAAS_ENVIRONMENT:
            ab_tests.SessionAbTest(ab_tests.DEMO_WORKFLOW_V2, request).update_response(response)
        return response

    def post(self, request, *args, **kwargs):
        if self.prefilled_email:
            meta = get_meta(request)
            track_clicked_signup_on_hubspot.delay(
                self.prefilled_email, request.COOKIES.get(HUBSPOT_COOKIE), meta)
        return super(UserRegistrationView, self).get(request, *args, **kwargs)

    @property
    def prefilled_email(self):
        return self.request.GET.get('e', '') or self.request.POST.get('e', '')

    @property
    def atypical_user(self):
        return self.request.GET.get('internal', False)

    @property
    def page_context(self):
        prefills = {
            'email': self.prefilled_email,
            'atypical_user': True if self.atypical_user else False
        }
        context = {
            'reg_form': RegisterWebUserForm(initial=prefills),
            'reg_form_defaults': prefills,
            'hide_password_feedback': has_custom_clean_password(),
            'professional_features': [
                _("Custom mobile app builder"),
                _("Powerful case management"),
                _("Field staff reports"),
                _("Unlimited mobile users"),
                _("Full suite of data tools"),
                _("3rd party integrations"),
                _("2-way SMS workflows"),
                _("Guaranteed tech support"),
                _("Access to Dimagi's Customer Success team"),
            ],
            'community_features': [
                _("Custom mobile app builder"),
                _("Basic case management"),
                _("Field staff reports"),
                _("5 mobile users"),
            ],
        }
        if settings.IS_SAAS_ENVIRONMENT:
            context['demo_workflow_ab_v2'] = ab_tests.SessionAbTest(
                ab_tests.DEMO_WORKFLOW_V2, self.request).context
        return context

    @property
    def page_url(self):
        return reverse(self.urlname)


class RegisterDomainView(TemplateView):

    template_name = 'registration/domain_request.html'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super(RegisterDomainView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if self.is_new_user:
            pending_domains = Domain.active_for_user(request.user, is_active=False)
            if len(pending_domains) > 0:
                context = get_domain_context()
                context.update({
                    'requested_domain': pending_domains[0],
                    'current_page': {'page_name': _('Confirm Account')},
                })
                return render(request, 'registration/confirmation_waiting.html', context)
        return super(RegisterDomainView, self).get(request, *args, **kwargs)

    @property
    def extra_context(self):
        invitations = [
            e for e in Invitation.by_email(self.request.user.username)
            if not e.is_expired
        ]
        return {
            'invitation_links': [{
                'domain': i.domain,
                'url': reverse("domain_accept_invitation", args=[i.domain, i.uuid]) + '?no_redirect=true',
            } for i in invitations],
            'show_multiple_invites': len(invitations) > 1,
        }

    @property
    @memoized
    def is_new_user(self):
        user = self.request.user
        return not (Domain.active_for_user(user) or user.is_superuser)

    def post(self, request, *args, **kwargs):
        referer_url = request.GET.get('referer', '')
        nextpage = request.POST.get('next')
        form = DomainRegistrationForm(request.POST)
        context = self.get_context_data(form=form)
        if not form.is_valid():
            return self.render_to_response(context)

        if settings.RESTRICT_DOMAIN_CREATION and not request.user.is_superuser:
            context.update({
                'current_page': {'page_name': _('Oops!')},
                'error_msg': _('Your organization has requested that project creation be restricted. '
                               'For more information, please speak to your administrator.'),
            })
            return render(request, 'error.html', context)

        reqs_today = RegistrationRequest.get_requests_today()
        max_req = settings.DOMAIN_MAX_REGISTRATION_REQUESTS_PER_DAY
        if reqs_today >= max_req:
            context.update({
                'current_page': {'page_name': _('Oops!')},
                'error_msg': _(
                    'Number of projects requested today exceeds limit (%d) - contact Dimagi'
                ) % max_req,
                'show_homepage_link': 1
            })
            return render(request, 'error.html', context)

        try:
            domain_name = request_new_domain(
                request,
                form.cleaned_data['hr_name'],
                is_new_user=self.is_new_user
            )
        except NameUnavailableException:
            context.update({
                'current_page': {'page_name': _('Oops!')},
                'error_msg': _('Project name already taken - please try another'),
                'show_homepage_link': 1
            })
            return render(request, 'error.html', context)
        except ErrorInitializingDomain as e:
            logging.error(f"Error initializing domain in RegisterDomainView: {str(e)}")
            context.update({
                'current_page': {'page_name': _('Oops!')},
                'error_msg': _('We encountered a temporary system issue. '
                               'Please try again in a few minutes. '
                               'If the issue persists, please contact support.'),
                'show_homepage_link': 1
            })
            return render(request, 'error.html', context)

        if self.is_new_user:
            context.update({
                'requested_domain': domain_name,
                'current_page': {'page_name': _('Confirm Account')},
            })
            track_workflow(self.request.user.email, "Created new project")
            return render(request, 'registration/confirmation_sent.html', context)

        if nextpage:
            return HttpResponseRedirect(nextpage)
        if referer_url:
            return redirect(referer_url)
        return HttpResponseRedirect(reverse("domain_homepage", args=[domain_name]))

    def get_context_data(self, **kwargs):
        request = self.request
        if (not request.couch_user) or request.couch_user.is_commcare_user():
            raise Http404()

        context = super(RegisterDomainView, self).get_context_data(**kwargs)
        context.update(get_domain_context())

        context.update({
            'form': kwargs.get('form') or DomainRegistrationForm(),
            'is_new_user': self.is_new_user,
        })
        return context


@transaction.atomic
@login_required
def resend_confirmation(request):
    try:
        dom_req = RegistrationRequest.get_request_for_username(request.user.username)
    except Exception:
        dom_req = None

    if not dom_req:
        inactive_domains_for_user = Domain.active_for_user(request.user, is_active=False)
        if len(inactive_domains_for_user) > 0:
            for domain in inactive_domains_for_user:
                domain.is_active = True
                domain.save()
        return redirect('domain_select')

    context = get_domain_context()
    default_page_name = _('Resend Confirmation Email')

    if request.method == 'POST':
        if (datetime.utcnow() - dom_req.request_time).seconds < CONFIRMATION_RESEND_LIMIT_SECONDS:
            context = {
                'message_body': _(f'Please wait at least {CONFIRMATION_RESEND_LIMIT_SECONDS} '
                                  f'seconds before requesting again.'),
                'current_page': {'page_name': default_page_name},
            }
            return render(request, 'registration/confirmation_error.html', context)
        try:
            dom_req.request_time = datetime.utcnow()
            dom_req.request_ip = get_ip(request)
            dom_req.save()
            send_domain_registration_email(dom_req.new_user_username,
                    dom_req.domain, dom_req.activation_guid,
                    request.user.get_full_name(), request.user.first_name)
        except Exception:
            context.update({
                'current_page': {'page_name': _('Oops!')},
                'error_msg': _('There was a problem with your request'),
                'show_homepage_link': 1,
            })
            return render(request, 'error.html', context)
        else:
            context.update({
                'requested_domain': dom_req.domain,
                'current_page': {'page_name': _('Confirmation Email Sent')},
            })
            return render(request, 'registration/confirmation_sent.html',
                context)

    context.update({
        'requested_domain': dom_req.domain,
        'current_page': {'page_name': default_page_name},
    })
    return render(request, 'registration/confirmation_resend.html', context)


@transaction.atomic
def confirm_domain(request, guid=''):
    with CriticalSection(['confirm_domain_' + guid]):
        error = None
        # Did we get a guid?
        if not guid:
            error = _('An account activation key was not provided.  If you think this '
                      'is an error, please contact the system administrator.')

        # Does guid exist in the system?
        else:
            req = RegistrationRequest.get_by_guid(guid)
            if not req:
                error = _('The account activation key "%s" provided is invalid. If you '
                          'think this is an error, please contact the system '
                          'administrator.') % guid

        if error is not None:
            context = {
                'message_body': error,
                'current_page': {'page_name': 'Account Not Activated'},
            }
            return render(request, 'registration/confirmation_error.html', context)

        requested_domain = Domain.get_by_name(req.domain)
        view_name = "dashboard_default"
        view_args = [requested_domain.name]

        # Has guid already been confirmed?
        if requested_domain.is_active:
            assert (req.confirm_time is not None and req.confirm_ip is not None)
            messages.success(request, 'Your account %s has already been activated. '
                'No further validation is required.' % req.new_user_username)
            return HttpResponseRedirect(reverse(view_name, args=view_args))

        # Set confirm time and IP; activate domain and new user who is in the
        req.confirm_time = datetime.utcnow()
        req.confirm_ip = get_ip(request)
        req.save()
        requested_domain.is_active = True
        requested_domain.save()
        requesting_user = WebUser.get_by_username(req.new_user_username)

        send_new_request_update_email(requesting_user, get_ip(request), requested_domain.name, is_confirming=True)

        messages.success(request,
                'Your account has been successfully activated.  Thank you for taking '
                'the time to confirm your email address: %s.'
            % (requesting_user.username))
        track_workflow(requesting_user.email, "Confirmed new project")
        track_confirmed_account_on_hubspot.delay(requesting_user.get_id)
        request.session['CONFIRM'] = True

        return HttpResponseRedirect(reverse(view_name, args=view_args))


@retry_resource(3)
def eula_agreement(request):
    if request.method == 'POST':
        current_user = CouchUser.from_django_user(request.user)
        if current_user.eula and not current_user.eula.signed:
            agreement = current_user.eula
            agreement.signed = True
            agreement.date = datetime.utcnow()
            agreement.user_ip = get_ip(request)
        else:
            new_agreement = LicenseAgreement(type="End User License Agreement", version=EULA_CURRENT_VERSION)
            new_agreement.signed = True
            new_agreement.date = datetime.utcnow()
            new_agreement.user_ip = get_ip(request)
            current_user.eulas.append(new_agreement)
        current_user.save()

    return HttpResponseRedirect(request.POST.get('next', '/'))


@login_required
@require_POST
def send_mobile_reminder(request):
    send_mobile_experience_reminder(request.couch_user.get_email(), request.couch_user.full_name,
                                    additional_email_context=project_logo_emails_context(None, request.couch_user))
    return HttpResponse()
