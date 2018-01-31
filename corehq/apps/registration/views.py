from __future__ import absolute_import
from datetime import datetime
import logging
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.urls import reverse
from django.db import transaction
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
import sys

from django.views.generic.base import TemplateView, View
from djangular.views.mixins import allow_remote_invocation, JSONResponseMixin

from corehq.apps.analytics import ab_tests
from corehq.apps.analytics.tasks import (
    track_workflow,
    track_confirmed_account_on_hubspot,
    track_clicked_signup_on_hubspot,
)
from corehq.apps.analytics.utils import get_meta
from corehq.apps.app_manager.dbaccessors import domain_has_apps
from corehq.apps.domain.decorators import login_required
from corehq.apps.domain.models import Domain
from corehq.apps.domain.exceptions import NameUnavailableException
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.registration.models import RegistrationRequest
from corehq.apps.registration.forms import DomainRegistrationForm, RegisterWebUserForm
from corehq.apps.registration.utils import activate_new_user, send_new_request_update_email, request_new_domain, \
    send_domain_registration_email
from corehq.apps.hqwebapp.decorators import use_jquery_ui, \
    use_ko_validation
from corehq.apps.users.models import WebUser, CouchUser
from django.contrib.auth.models import User
from dimagi.utils.couch.resource_conflict import retry_resource
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.web import get_ip
from corehq.util.context_processors import get_per_domain_context


def get_domain_context():
    return get_per_domain_context(Domain())


def registration_default(request):
    return redirect(UserRegistrationView.urlname)


class NewUserNumberAbTestMixin__Enabled(object):
    @property
    @memoized
    def _ab_show_number(self):
        return ab_tests.ABTest(ab_tests.NEW_USER_NUMBER, self.request)

    @property
    def ab_show_number(self):
        return self._ab_show_number.version == ab_tests.NEW_USER_NUMBER_OPTION_SHOW_NUM

    @property
    def ab_show_number_context(self):
        return self._ab_show_number.context

    def ab_show_number_update_response(self, response):
        self._ab_show_number.update_response(response)


class NewUserNumberAbTestMixin__NoAbEnabled(object):
    @property
    @memoized
    def _ab_show_number(self):
        return None

    @property
    def ab_show_number(self):
        return True

    @property
    def ab_show_number_context(self):
        return None

    def ab_show_number_update_response(self, response):
        pass


class NewUserNumberAbTestMixin__Disabled(object):
    @property
    def ab_show_number(self):
        return False

    @property
    def ab_show_number_context(self):
        return None

    def ab_show_number_update_response(self, response):
        pass


NewUserNumberAbTestMixin = NewUserNumberAbTestMixin__NoAbEnabled


class NewUserProfileFieldAbTestMixin(object):
    @property
    @memoized
    def ab_persona_field(self):
        return ab_tests.ABTest(ab_tests.NEW_USER_PERSONA_FIELD, self.request)

    @property
    def ab_show_persona(self):
        return self.ab_persona_field.version == ab_tests.NEW_USER_PERSONA_OPTION_SHOW


class ProcessRegistrationView(JSONResponseMixin, NewUserNumberAbTestMixin,
                              NewUserProfileFieldAbTestMixin, View):
    urlname = 'process_registration'

    def get(self, request, *args, **kwargs):
        raise Http404()

    def _create_new_account(self, reg_form):
        activate_new_user(reg_form, ip=get_ip(self.request))
        new_user = authenticate(
            username=reg_form.cleaned_data['email'],
            password=reg_form.cleaned_data['password']
        )
        if 'phone_number' in reg_form.cleaned_data and reg_form.cleaned_data['phone_number']:
            web_user = WebUser.get_by_username(new_user.username)
            web_user.phone_numbers.append(reg_form.cleaned_data['phone_number'])
            web_user.save()
        track_workflow(new_user.email, "Requested new account")
        login(self.request, new_user)

    @allow_remote_invocation
    def register_new_user(self, data):
        reg_form = RegisterWebUserForm(
            data['data'],
            show_number=self.ab_show_number,
            show_persona=self.ab_show_persona,
        )
        if reg_form.is_valid():
            self._create_new_account(reg_form)
            try:
                request_new_domain(
                    self.request, reg_form, is_new_user=True
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
            return {
                'success': True,
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
        return {
            'isValid': not is_existing,
        }


class UserRegistrationView(NewUserNumberAbTestMixin,
                           NewUserProfileFieldAbTestMixin, BasePageView):
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
        self.ab_show_number_update_response(response)
        self.ab_persona_field.update_response(response)
        return response

    def post(self, request, *args, **kwargs):
        if self.prefilled_email:
            meta = get_meta(request)
            track_clicked_signup_on_hubspot.delay(self.prefilled_email, request.COOKIES, meta)
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
        return {
            'reg_form': RegisterWebUserForm(
                initial=prefills,
                show_number=self.ab_show_number,
                show_persona=self.ab_show_persona,
            ),
            'reg_form_defaults': prefills,
            'hide_password_feedback': settings.ENABLE_DRACONIAN_SECURITY_FEATURES,
            'implement_password_obfuscation': settings.OBFUSCATE_PASSWORD_FOR_NIC_COMPLIANCE,
            'show_number': self.ab_show_number,
            'ab_show_number': self.ab_show_number_context,
            'ab_persona_field': self.ab_persona_field.context,
        }

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
    @memoized
    def is_new_user(self):
        user = self.request.user
        return not (Domain.active_for_user(user) or user.is_superuser)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        referer_url = request.GET.get('referer', '')
        nextpage = request.POST.get('next')
        form = DomainRegistrationForm(request.POST)
        context = self.get_context_data(form=form)
        if not form.is_valid():
            return self.render_to_response(context)

        if settings.RESTRICT_DOMAIN_CREATION and not request.user.is_superuser:
            context.update({
                'current_page': {'page_name': ('Oops!')},
                'error_msg': ('Your organization has requested that domain creation should be restricted. '
                              'For more information, please speak to your administrator.'),
            })
            return render(request, 'error.html', context)

        reqs_today = RegistrationRequest.get_requests_today()
        max_req = settings.DOMAIN_MAX_REGISTRATION_REQUESTS_PER_DAY
        if reqs_today >= max_req:
            context.update({
                'current_page': {'page_name': _('Oops!')},
                'error_msg': _(
                    'Number of domains requested today exceeds limit (%d) - contact Dimagi'
                ) % max_req,
                'show_homepage_link': 1
            })
            return render(request, 'error.html', context)

        try:
            domain_name = request_new_domain(request, form, is_new_user=self.is_new_user)
        except NameUnavailableException:
            context.update({
                'current_page': {'page_name': _('Oops!')},
                'error_msg': _('Project name already taken - please try another'),
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

    if request.method == 'POST':
        try:
            send_domain_registration_email(dom_req.new_user_username,
                    dom_req.domain, dom_req.activation_guid,
                    request.user.get_full_name())
        except Exception:
            context.update({
                'current_page': {'page_name': _('Oops!')},
                'error_msg': _('There was a problem with your request'),
                'error_details': sys.exc_info(),
                'show_homepage_link': 1,
            })
            return render(request, 'error.html', context)
        else:
            context.update({
                'requested_domain': dom_req.domain,
                'current_page': {'page_name': ('Confirmation Email Sent')},
            })
            return render(request, 'registration/confirmation_sent.html',
                context)

    context.update({
        'requested_domain': dom_req.domain,
        'current_page': {'page_name': _('Resend Confirmation Email')},
    })
    return render(request, 'registration/confirmation_resend.html', context)


@transaction.atomic
def confirm_domain(request, guid=None):
    error = None
    # Did we get a guid?
    if guid is None:
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
    if not domain_has_apps(req.domain):
        view_name = "default_new_app"

    # Has guid already been confirmed?
    if requested_domain.is_active:
        assert(req.confirm_time is not None and req.confirm_ip is not None)
        messages.success(request, 'Your account %s has already been activated. '
            'No further validation is required.' % req.new_user_username)
        return HttpResponseRedirect(reverse(view_name, args=[requested_domain]))

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
    track_confirmed_account_on_hubspot.delay(requesting_user)
    request.session['CONFIRM'] = True
    return HttpResponseRedirect(reverse(view_name, args=[requested_domain]))


@retry_resource(3)
def eula_agreement(request):
    if request.method == 'POST':
        current_user = CouchUser.from_django_user(request.user)
        current_user.eula.signed = True
        current_user.eula.date = datetime.utcnow()
        current_user.eula.user_ip = get_ip(request)
        current_user.save()

    return HttpResponseRedirect(request.POST.get('next', '/'))
