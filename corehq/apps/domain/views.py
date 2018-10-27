from __future__ import absolute_import
from __future__ import unicode_literals
import copy
import datetime
from collections import defaultdict, namedtuple
from decimal import Decimal
import logging
import json
import io
import csv342 as csv

from couchdbkit import ResourceNotFound
import dateutil
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET
from django.views.generic import View
from django.db.models import Sum
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.http import urlsafe_base64_decode
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.shortcuts import redirect, render
from django.contrib import messages
from django.contrib.auth.views import password_reset_confirm
from django.views.decorators.http import require_POST
from PIL import Image
from django.utils.translation import ugettext as _, ugettext_lazy
from django.contrib.auth.models import User

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.calendar_fixture.forms import CalendarFixtureForm
from corehq.apps.calendar_fixture.models import CalendarFixtureSettings
from corehq.apps.case_search.models import (
    CaseSearchConfig,
    FuzzyProperties,
    IgnorePatterns,
    enable_case_search,
    disable_case_search,
)
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_js_domain_cachebuster
from corehq.apps.linked_domain.dbaccessors import get_domain_master_link
from corehq.apps.locations.permissions import location_safe
from corehq.apps.locations.forms import LocationFixtureForm
from corehq.apps.locations.models import LocationFixtureConfiguration
from corehq.const import USER_DATE_FORMAT
from corehq.apps.accounting.async_handlers import Select2BillingInfoHandler
from corehq.apps.accounting.invoicing import DomainWireInvoiceFactory
from corehq.apps.hqwebapp.tasks import send_mail_async
from corehq.apps.hqwebapp.decorators import (
    use_jquery_ui,
    use_select2,
    use_select2_v4,
    use_multiselect,
)
from corehq.apps.accounting.exceptions import (
    NewSubscriptionError,
    PaymentRequestError,
    SubscriptionAdjustmentError,
)
from corehq.apps.accounting.payment_handlers import (
    BulkStripePaymentHandler,
    CreditStripePaymentHandler,
    InvoiceStripePaymentHandler,
)
from corehq.apps.accounting.subscription_changes import DomainDowngradeStatusHandler
from corehq.apps.accounting.forms import EnterprisePlanContactForm, AnnualPlanContactForm
from corehq.apps.accounting.utils import (
    get_change_status, get_privileges, fmt_dollar_amount,
    quantize_accounting_decimal, get_customer_cards,
    log_accounting_error, domain_has_privilege, is_downgrade
)
from corehq.apps.hqwebapp.async_handler import AsyncHandlerMixin
from corehq.apps.smsbillables.async_handlers import SMSRatesAsyncHandler, SMSRatesSelect2AsyncHandler
from corehq.apps.smsbillables.forms import SMSRateCalculatorForm
from corehq.apps.toggle_ui.views import ToggleEditView
from corehq.apps.users.models import Invitation, CouchUser, Permissions
from corehq.apps.fixtures.models import FixtureDataType
from corehq.toggles import NAMESPACE_DOMAIN, all_toggles, CAN_EDIT_EULA, TRANSFER_DOMAIN, NAMESPACE_USER
from custom.openclinica.forms import OpenClinicaSettingsForm
from custom.openclinica.models import OpenClinicaSettings
from dimagi.utils.couch.resource_conflict import retry_resource
from dimagi.utils.web import json_request
from corehq import privileges, feature_previews
from django_prbac.utils import has_privilege
from corehq.apps.accounting.models import (
    Subscription, CreditLine, SubscriptionType,
    DefaultProductPlan, SoftwarePlanEdition, BillingAccount,
    BillingAccountType,
    Invoice, BillingRecord, InvoicePdf, PaymentMethodType,
    EntryPoint, WireInvoice, CustomerInvoice,
    StripePaymentMethod, LastPayment,
    UNLIMITED_FEATURE_USAGE, MINIMUM_SUBSCRIPTION_LENGTH
)
from corehq.apps.accounting.usage import FeatureUsageCalculator
from corehq.apps.accounting.user_text import (
    get_feature_name,
    DESC_BY_EDITION,
    get_feature_recurring_interval,
)
from corehq.apps.domain.calculations import CALCS, CALC_FNS, CALC_ORDER, dom_calc
from corehq.apps.domain.decorators import (
    domain_admin_required, login_required, require_superuser, login_and_domain_required
)
from corehq.apps.domain.forms import (
    DomainGlobalSettingsForm, DomainMetadataForm, SnapshotSettingsForm,
    SnapshotApplicationForm, DomainInternalForm, PrivacySecurityForm,
    ConfirmNewSubscriptionForm, ProBonoForm, EditBillingAccountInfoForm,
    ConfirmSubscriptionRenewalForm, SnapshotFixtureForm, TransferDomainForm,
    SelectSubscriptionTypeForm, INTERNAL_SUBSCRIPTION_MANAGEMENT_FORMS, AdvancedExtendedTrialForm,
    ContractedPartnerForm, DimagiOnlyEnterpriseForm, USE_PARENT_LOCATION_CHOICE,
    USE_LOCATION_CHOICE)
from corehq.apps.domain.models import (
    Domain,
    LICENSES,
    TransferDomainRequest,
)
from corehq.apps.domain.utils import normalize_domain_name, send_repeater_payloads
from corehq.apps.hqwebapp.views import BaseSectionPageView, BasePageView, CRUDPaginatedViewMixin
from corehq.apps.domain.forms import ProjectSettingsForm
from memoized import memoized
from dimagi.utils.web import get_ip, json_response, get_site_domain

from corehq.apps.users.decorators import require_can_edit_web_users, require_permission
from toggle.models import Toggle
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.hqwebapp.signals import clear_login_attempts
from corehq.apps.ota.models import MobileRecoveryMeasure
import six
from six.moves import map


class BaseProjectSettingsView(BaseDomainView):
    section_name = ugettext_lazy("Project Settings")
    template_name = "settings/base_template.html"

    @property
    def main_context(self):
        main_context = super(BaseProjectSettingsView, self).main_context
        main_context.update({
            'is_project_settings': True,
        })
        return main_context

    @property
    @memoized
    def section_url(self):
        return reverse(EditBasicProjectInfoView.urlname, args=[self.domain])


class DefaultProjectSettingsView(BaseDomainView):
    urlname = 'domain_settings_default'

    def get(self, request, *args, **kwargs):
        if request.couch_user.is_domain_admin(self.domain):
            return HttpResponseRedirect(reverse(EditBasicProjectInfoView.urlname, args=[self.domain]))
        return HttpResponseRedirect(reverse(EditMyProjectSettingsView.urlname, args=[self.domain]))


class BaseAdminProjectSettingsView(BaseProjectSettingsView):
    """
        The base class for all project settings views that require administrative
        access.
    """

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseProjectSettingsView, self).dispatch(request, *args, **kwargs)


class BaseEditProjectInfoView(BaseAdminProjectSettingsView):
    """
        The base class for all the edit project information views.
    """
    strict_domain_fetching = True

    @property
    def main_context(self):
        context = super(BaseEditProjectInfoView, self).main_context
        context.update({
            'commtrack_enabled': self.domain_object.commtrack_enabled,
            # ideally the template gets access to the domain doc through
            # some other means. otherwise it has to be supplied to every view reachable in that sidebar (every
            # view whose template extends users_base.html); mike says he's refactoring all of this imminently, so
            # i will not worry about it until he is done
            'call_center_enabled': self.domain_object.call_center_config.enabled,
            'cloudcare_releases':  self.domain_object.cloudcare_releases,
        })
        return context


class EditBasicProjectInfoView(BaseEditProjectInfoView):
    template_name = 'domain/admin/info_basic.html'
    urlname = 'domain_basic_info'
    page_title = ugettext_lazy("Basic")

    @method_decorator(domain_admin_required)
    @use_select2
    def dispatch(self, request, *args, **kwargs):
        return super(BaseProjectSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    def can_user_see_meta(self):
        return self.request.couch_user.is_previewer()

    @property
    def can_use_custom_logo(self):
        return has_privilege(self.request, privileges.CUSTOM_BRANDING)

    @property
    @memoized
    def basic_info_form(self):
        initial = {
            'hr_name': self.domain_object.hr_name or self.domain_object.name,
            'project_description': self.domain_object.project_description,
            'default_timezone': self.domain_object.default_timezone,
            'case_sharing': json.dumps(self.domain_object.case_sharing),
            'call_center_enabled': self.domain_object.call_center_config.enabled,
            'call_center_type': self.initial_call_center_type,
            'call_center_case_owner': self.initial_call_center_case_owner,
            'call_center_case_type': self.domain_object.call_center_config.case_type,
            'commtrack_enabled': self.domain_object.commtrack_enabled,
            'mobile_ucr_sync_interval': self.domain_object.default_mobile_ucr_sync_interval
        }
        if self.can_user_see_meta:
            initial.update({
                'is_test': self.domain_object.is_test,
                'cloudcare_releases': self.domain_object.cloudcare_releases,
            })
            form_cls = DomainMetadataForm
        else:
            form_cls = DomainGlobalSettingsForm

        if self.request.method == 'POST':
            return form_cls(
                self.request.POST,
                self.request.FILES,
                domain=self.domain_object,
                can_use_custom_logo=self.can_use_custom_logo,
            )

        return form_cls(
            initial=initial,
            domain=self.domain_object,
            can_use_custom_logo=self.can_use_custom_logo
        )

    @property
    @memoized
    def initial_call_center_case_owner(self):
        config = self.domain_object.call_center_config
        if config.use_user_location_as_owner:
            if config.user_location_ancestor_level == 1:
                return USE_PARENT_LOCATION_CHOICE
            return USE_LOCATION_CHOICE
        return self.domain_object.call_center_config.case_owner_id

    @property
    @memoized
    def initial_call_center_type(self):
        if self.domain_object.call_center_config.use_fixtures:
            return DomainGlobalSettingsForm.CASES_AND_FIXTURES_CHOICE
        return DomainGlobalSettingsForm.CASES_ONLY_CHOICE

    @property
    def page_context(self):
        return {
            'basic_info_form': self.basic_info_form,
        }

    def post(self, request, *args, **kwargs):
        if self.basic_info_form.is_valid():
            if self.basic_info_form.save(request, self.domain_object):
                messages.success(request, _("Project settings saved!"))
            else:
                messages.error(request, _("There seems to have been an error saving your settings. Please try again!"))
            return HttpResponseRedirect(self.page_url)

        return self.get(request, *args, **kwargs)


class EditMyProjectSettingsView(BaseProjectSettingsView):
    template_name = 'domain/admin/my_project_settings.html'
    urlname = 'my_project_settings'
    page_title = ugettext_lazy("My Timezone")

    @method_decorator(login_and_domain_required)
    def dispatch(self, *args, **kwargs):
        return super(LoginAndDomainMixin, self).dispatch(*args, **kwargs)

    @property
    @memoized
    def my_project_settings_form(self):
        initial = { 'global_timezone': self.domain_object.default_timezone }
        if self.domain_membership:
            initial.update({
                'override_global_tz': self.domain_membership.override_global_tz,
                'user_timezone': (self.domain_membership.timezone if self.domain_membership.override_global_tz
                                  else self.domain_object.default_timezone),
            })
        else:
            initial.update({
                'override_global_tz': False,
                'user_timezone': initial["global_timezone"],
            })

        if self.request.method == 'POST':
            return ProjectSettingsForm(self.request.POST, initial=initial)
        return ProjectSettingsForm(initial=initial)

    @property
    @memoized
    def domain_membership(self):
        return self.request.couch_user.get_domain_membership(self.domain)

    @property
    def page_context(self):
        return {
            'my_project_settings_form': self.my_project_settings_form,
            'override_global_tz': self.domain_membership.override_global_tz if self.domain_membership else False,
            'no_domain_membership': not self.domain_membership,
        }

    def post(self, request, *args, **kwargs):
        if self.my_project_settings_form.is_valid():
            self.my_project_settings_form.save(self.request.couch_user, self.domain)
            messages.success(request, _("Your project settings have been saved!"))
        return self.get(request, *args, **kwargs)


class EditOpenClinicaSettingsView(BaseProjectSettingsView):
    template_name = 'domain/admin/openclinica_settings.html'
    urlname = 'oc_settings'
    page_title = ugettext_lazy('OpenClinica settings')

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseProjectSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def openclinica_settings_form(self):
        oc_settings = OpenClinicaSettings.for_domain(self.domain_object.name)
        initial = dict(oc_settings.study) if oc_settings else {}
        if self.request.method == 'POST':
            return OpenClinicaSettingsForm(self.request.POST, initial=initial)
        return OpenClinicaSettingsForm(initial=initial)

    @property
    def page_context(self):
        return {'openclinica_settings_form': self.openclinica_settings_form}

    @method_decorator(sensitive_post_parameters('username', 'password'))
    def post(self, request, *args, **kwargs):
        if self.openclinica_settings_form.is_valid():
            if self.openclinica_settings_form.save(self.domain_object):
                messages.success(request, _('OpenClinica settings successfully updated'))
            else:
                messages.error(request, _('An error occurred. Please try again.'))
        return self.get(request, *args, **kwargs)


@location_safe
def logo(request, domain):
    logo = Domain.get_by_name(domain).get_custom_logo()
    if logo is None:
        raise Http404()

    return HttpResponse(logo[0], content_type=logo[1])


class EditPrivacySecurityView(BaseAdminProjectSettingsView):
    template_name = "domain/admin/project_privacy.html"
    urlname = "privacy_info"
    page_title = ugettext_lazy("Privacy and Security")

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseProjectSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def privacy_form(self):
        initial = {
            "secure_submissions": self.domain_object.secure_submissions,
            "restrict_superusers": self.domain_object.restrict_superusers,
            "allow_domain_requests": self.domain_object.allow_domain_requests,
            "hipaa_compliant": self.domain_object.hipaa_compliant,
            "secure_sessions": self.domain_object.secure_sessions,
            "two_factor_auth": self.domain_object.two_factor_auth,
            "strong_mobile_passwords": self.domain_object.strong_mobile_passwords,
        }
        if self.request.method == 'POST':
            return PrivacySecurityForm(self.request.POST, initial=initial,
                                       user_name=self.request.couch_user.username,
                                       domain=self.request.domain)
        return PrivacySecurityForm(initial=initial, user_name=self.request.couch_user.username,
                                   domain=self.request.domain)

    @property
    def page_context(self):
        return {
            'privacy_form': self.privacy_form
        }

    def post(self, request, *args, **kwargs):
        if self.privacy_form.is_valid():
            self.privacy_form.save(self.domain_object)
            messages.success(request, _("Your project settings have been saved!"))
        return self.get(request, *args, **kwargs)


class ManageProjectMediaView(BaseAdminProjectSettingsView):
    urlname = 'domain_manage_multimedia'
    page_title = ugettext_lazy("Multimedia Sharing")
    template_name = 'domain/admin/media_manager.html'

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseProjectSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    def project_media_data(self):
        return [{
            'license': m.license.type if m.license else 'public',
            'shared': self.domain in m.shared_by,
            'url': m.url(),
            'm_id': m._id,
            'tags': m.tags.get(self.domain, []),
            'type': m.doc_type,
        } for m in self.request.project.all_media()]

    @property
    def page_context(self):
        return {
            'media': self.project_media_data,
            'licenses': list(LICENSES.items()),
        }

    @retry_resource(3)
    def post(self, request, *args, **kwargs):
        for m_file in request.project.all_media():
            if '%s_tags' % m_file._id in request.POST:
                m_file.tags[self.domain] = request.POST.get('%s_tags' % m_file._id, '').split(' ')

            if self.domain not in m_file.shared_by and request.POST.get('%s_shared' % m_file._id, False):
                m_file.shared_by.append(self.domain)
            elif self.domain in m_file.shared_by and not request.POST.get('%s_shared' % m_file._id, False):
                m_file.shared_by.remove(self.domain)

            if '%s_license' % m_file._id in request.POST:
                m_file.update_or_add_license(self.domain,
                                             type=request.POST.get('%s_license' % m_file._id, 'public'),
                                             should_save=True)
            m_file.save()
        messages.success(request, _("Multimedia updated successfully!"))
        return self.get(request, *args, **kwargs)


class CaseSearchConfigView(BaseAdminProjectSettingsView):
    urlname = 'case_search_config'
    page_title = ugettext_lazy('Case Search')
    template_name = 'domain/admin/case_search.html'

    @method_decorator(domain_admin_required)
    @method_decorator(toggles.SYNC_SEARCH_CASE_CLAIM.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(CaseSearchConfigView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        request_json = json.loads(request.body)
        enable = request_json.get('enable')
        fuzzies_by_casetype = request_json.get('fuzzy_properties')
        updated_fuzzies = []
        for case_type, properties in six.iteritems(fuzzies_by_casetype):
            fp, created = FuzzyProperties.objects.get_or_create(
                domain=self.domain,
                case_type=case_type
            )
            fp.properties = properties
            fp.save()
            updated_fuzzies.append(fp)

        unneeded_fuzzies = FuzzyProperties.objects.filter(domain=self.domain).exclude(
            case_type__in=list(fuzzies_by_casetype)
        )
        unneeded_fuzzies.delete()

        ignore_patterns = request_json.get('ignore_patterns')
        updated_ignore_patterns = []
        update_ignore_pattern_ids = []
        for ignore_pattern_regex in ignore_patterns:
            rc, created = IgnorePatterns.objects.get_or_create(
                domain=self.domain,
                case_type=ignore_pattern_regex.get('case_type'),
                case_property=ignore_pattern_regex.get('case_property'),
                regex=ignore_pattern_regex.get('regex')
            )
            updated_ignore_patterns.append(rc)
            update_ignore_pattern_ids.append(rc.pk)

        unneeded_ignore_patterns = IgnorePatterns.objects.filter(domain=self.domain).exclude(
            pk__in=update_ignore_pattern_ids
        )
        unneeded_ignore_patterns.delete()

        if enable:
            enable_case_search(self.domain)
        else:
            disable_case_search(self.domain)

        CaseSearchConfig.objects.update_or_create(domain=self.domain, defaults={
            'enabled': request_json.get('enable'),
            'fuzzy_properties': updated_fuzzies,
            'ignore_patterns': updated_ignore_patterns,
        })
        return json_response(self.page_context)

    @property
    def page_context(self):
        apps = get_apps_in_domain(self.domain, include_remote=False)
        case_types = {t for app in apps for t in app.get_case_types() if t}
        current_values = CaseSearchConfig.objects.get_or_none(pk=self.domain)
        return {
            'case_types': sorted(list(case_types)),
            'values': {
                'enabled': current_values.enabled if current_values else False,
                'fuzzy_properties': {
                    fp.case_type: fp.properties for fp in current_values.fuzzy_properties.all()
                } if current_values else {},
                'ignore_patterns': [{
                    'case_type': rc.case_type,
                    'case_property': rc.case_property,
                    'regex': rc.regex
                } for rc in current_values.ignore_patterns.all()] if current_values else {}
            }
        }


class BaseInternalDomainSettingsView(BaseProjectSettingsView):
    strict_domain_fetching = True

    @method_decorator(login_and_domain_required)
    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseInternalDomainSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    def main_context(self):
        context = super(BaseInternalDomainSettingsView, self).main_context
        context.update({
            'project': self.domain_object,
        })
        return context

    @property
    def page_name(self):
        return mark_safe("%s <small>Internal</small>" % self.page_title)


class EditInternalDomainInfoView(BaseInternalDomainSettingsView):
    urlname = 'domain_internal_settings'
    page_title = ugettext_lazy("Project Information")
    template_name = 'domain/internal_settings.html'
    strict_domain_fetching = True

    @method_decorator(login_and_domain_required)
    @method_decorator(require_superuser)
    @use_jquery_ui  # datepicker
    @use_multiselect
    def dispatch(self, request, *args, **kwargs):
        return super(BaseInternalDomainSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def internal_settings_form(self):
        can_edit_eula = CAN_EDIT_EULA.enabled(self.request.couch_user.username)
        if self.request.method == 'POST':
            return DomainInternalForm(self.request.domain, can_edit_eula, self.request.POST)
        initial = {
            'countries': self.domain_object.deployment.countries,
            'is_test': self.domain_object.is_test,
            'use_custom_auto_case_update_limit': 'Y' if self.domain_object.auto_case_update_limit else 'N',
            'auto_case_update_limit': self.domain_object.auto_case_update_limit,
            'granted_messaging_access': self.domain_object.granted_messaging_access,
        }
        internal_attrs = [
            'sf_contract_id',
            'sf_account_id',
            'initiative',
            'self_started',
            'area',
            'sub_area',
            'organization_name',
            'notes',
            'phone_model',
            'commtrack_domain',
            'performance_threshold',
            'experienced_threshold',
            'amplifies_workers',
            'amplifies_project',
            'data_access_threshold',
            'business_unit',
            'workshop_region',
            'partner_technical_competency',
            'support_prioritization',
            'gs_continued_involvement',
            'technical_complexity',
            'app_design_comments',
            'training_materials',
            'partner_comments',
            'partner_contact',
            'dimagi_contact',
        ]
        if can_edit_eula:
            internal_attrs += [
                'custom_eula',
                'can_use_data',
            ]
        for attr in internal_attrs:
            val = getattr(self.domain_object.internal, attr)
            if isinstance(val, bool):
                val = 'true' if val else 'false'
            initial[attr] = val
        return DomainInternalForm(self.request.domain, can_edit_eula, initial=initial)

    @property
    def page_context(self):
        return {
            'project': self.domain_object,
            'form': self.internal_settings_form,
            'areas': dict([(a["name"], a["sub_areas"]) for a in settings.INTERNAL_DATA["area"]]),
        }

    def send_handoff_email(self):
        partner_contact = self.internal_settings_form.cleaned_data['partner_contact']
        dimagi_contact = self.internal_settings_form.cleaned_data['dimagi_contact']
        recipients = [partner_contact, dimagi_contact]
        params = {'contact_name': CouchUser.get_by_username(dimagi_contact).human_friendly_name}
        send_html_email_async.delay(
            subject="Project Support Transition",
            recipient=recipients,
            html_content=render_to_string(
                "domain/email/support_handoff.html", params),
            text_content=render_to_string(
                "domain/email/support_handoff.txt", params),
            email_from=settings.SUPPORT_EMAIL,
        )
        messages.success(self.request,
                         _("Sent hand-off email to {}.").format(" and ".join(recipients)))

    def post(self, request, *args, **kwargs):
        if self.internal_settings_form.is_valid():
            old_attrs = copy.copy(self.domain_object.internal)
            self.internal_settings_form.save(self.domain_object)
            eula_props_changed = (bool(old_attrs.custom_eula) != bool(self.domain_object.internal.custom_eula) or
                                  bool(old_attrs.can_use_data) != bool(self.domain_object.internal.can_use_data))

            if eula_props_changed and settings.EULA_CHANGE_EMAIL:
                message = '\n'.join([
                    '{user} changed either the EULA or data sharing properties for domain {domain}.',
                    '',
                    'The properties changed were:',
                    '- Custom eula: {eula_old} --> {eula_new}',
                    '- Can use data: {can_use_data_old} --> {can_use_data_new}'
                ]).format(
                    user=self.request.couch_user.username,
                    domain=self.domain,
                    eula_old=old_attrs.custom_eula,
                    eula_new=self.domain_object.internal.custom_eula,
                    can_use_data_old=old_attrs.can_use_data,
                    can_use_data_new=self.domain_object.internal.can_use_data,
                )
                send_mail_async.delay(
                    'Custom EULA or data use flags changed for {}'.format(self.domain),
                    message, settings.DEFAULT_FROM_EMAIL, [settings.EULA_CHANGE_EMAIL]
                )

            messages.success(request, _("The internal information for project %s was successfully updated!")
                                      % self.domain)
            if self.internal_settings_form.cleaned_data['send_handoff_email']:
                self.send_handoff_email()
            return redirect(self.urlname, self.domain)
        else:
            messages.error(request, _(
                "Your settings are not valid, see below for errors. Correct them and try again!"))
            return self.get(request, *args, **kwargs)


class EditInternalCalculationsView(BaseInternalDomainSettingsView):
    urlname = 'domain_internal_calculations'
    page_title = ugettext_lazy("Calculated Properties")
    template_name = 'domain/internal_calculations.html'

    @method_decorator(login_and_domain_required)
    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseInternalDomainSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            'calcs': CALCS,
            'order': CALC_ORDER,
        }


@login_and_domain_required
@require_superuser
@require_GET
def toggle_diff(request, domain):
    params = json_request(request.GET)
    other_domain = params.get('domain')
    diff = []
    if Domain.get_by_name(other_domain):
        diff = [{'slug': t.slug, 'label': t.label, 'url': reverse(ToggleEditView.urlname, args=[t.slug])}
                for t in feature_previews.all_previews() + all_toggles()
                if t.enabled(request.domain, NAMESPACE_DOMAIN) and not t.enabled(other_domain, NAMESPACE_DOMAIN)]
        diff.sort(cmp=lambda x, y: cmp(x['label'], y['label']))
    return json_response(diff)


@login_and_domain_required
@require_superuser
def calculated_properties(request, domain):
    calc_tag = request.GET.get("calc_tag", '').split('--')
    extra_arg = calc_tag[1] if len(calc_tag) > 1 else ''
    calc_tag = calc_tag[0]

    if not calc_tag or calc_tag not in list(CALC_FNS):
        data = {"error": 'This tag does not exist'}
    else:
        data = {"value": dom_calc(calc_tag, domain, extra_arg)}
    return json_response(data)


class FeaturePreviewsView(BaseAdminProjectSettingsView):
    urlname = 'feature_previews'
    page_title = ugettext_lazy("Feature Previews")
    template_name = 'domain/admin/feature_previews.html'

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseProjectSettingsView, self).dispatch(request, *args, **kwargs)

    @memoized
    def features(self):
        features = []
        for preview_name in dir(feature_previews):
            if not preview_name.startswith('__'):
                preview = getattr(feature_previews, preview_name)
                if isinstance(preview, feature_previews.FeaturePreview) and preview.has_privilege(self.request):
                    features.append((preview, preview.enabled(self.domain)))

        return sorted(features, key=lambda feature: feature[0].label)

    def get_toggle(self, slug):
        if not slug in [f.slug for f, _ in self.features()]:
            raise Http404()
        try:
            return Toggle.get(slug)
        except ResourceNotFound:
            return Toggle(slug=slug)

    @property
    def page_context(self):
        exclude_previews = ['advanced_itemsets', 'calc_xpaths', 'conditional_enum', 'enum_image']
        return {
            'features': [f for f in self.features() if f[0].slug not in exclude_previews],
        }

    def post(self, request, *args, **kwargs):
        for feature, enabled in self.features():
            self.update_feature(feature, enabled, feature.slug in request.POST)
        feature_previews.previews_dict.clear(self.domain)

        return redirect('feature_previews', domain=self.domain)

    def update_feature(self, feature, current_state, new_state):
        if current_state != new_state:
            toggle_js_domain_cachebuster.clear(self.domain)
            feature.set(self.domain, new_state, NAMESPACE_DOMAIN)
            if feature.save_fn is not None:
                feature.save_fn(self.domain, new_state)


class FlagsAndPrivilegesView(BaseAdminProjectSettingsView):
    urlname = 'feature_flags_and_privileges'
    page_title = ugettext_lazy("Feature Flags and Privileges")
    template_name = 'domain/admin/flags_and_privileges.html'

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(FlagsAndPrivilegesView, self).dispatch(request, *args, **kwargs)

    @memoized
    def enabled_flags(self):
        def _sort_key(toggle_enabled_tuple):
            return (not toggle_enabled_tuple[1], not toggle_enabled_tuple[2], toggle_enabled_tuple[0].label)
        unsorted_toggles = [(
            toggle,
            toggle.enabled(self.domain, namespace=NAMESPACE_DOMAIN),
            toggle.enabled(self.request.couch_user.username, namespace=NAMESPACE_USER)
        ) for toggle in all_toggles()]
        return sorted(unsorted_toggles, key=_sort_key)

    def _get_privileges(self):
        return sorted([
            (privileges.Titles.get_name_from_privilege(privilege),
             domain_has_privilege(self.domain, privilege))
            for privilege in privileges.MAX_PRIVILEGES
        ], key=lambda name_has: (not name_has[1], name_has[0]))

    @property
    def page_context(self):
        return {
            'flags': self.enabled_flags(),
            'use_sql_backend': self.domain_object.use_sql_backend,
            'privileges': self._get_privileges(),
        }


class TransferDomainView(BaseAdminProjectSettingsView):
    urlname = 'transfer_domain_view'
    page_title = ugettext_lazy("Transfer Project")
    template_name = 'domain/admin/transfer_domain.html'

    @property
    @memoized
    def active_transfer(self):
        return TransferDomainRequest.get_active_transfer(self.domain,
                                                         self.request.user.username)

    @property
    @memoized
    def transfer_domain_form(self):
        return TransferDomainForm(self.domain,
                                  self.request.user.username,
                                  self.request.POST or None)

    def get(self, request, *args, **kwargs):

        if self.active_transfer:
            self.template_name = 'domain/admin/transfer_domain_pending.html'

            if request.GET.get('resend', None):
                self.active_transfer.send_transfer_request()
                messages.info(request,
                              _("Resent transfer request for project '{domain}'").format(domain=self.domain))

        return super(TransferDomainView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        form = self.transfer_domain_form
        if form.is_valid():
            # Initiate domain transfer
            transfer = form.save()
            transfer.send_transfer_request()
            return HttpResponseRedirect(self.page_url)

        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    @property
    def page_context(self):
        if self.active_transfer:
            return {'transfer': self.active_transfer.as_dict()}
        else:
            return {'form': self.transfer_domain_form}

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        if not TRANSFER_DOMAIN.enabled(request.domain):
            raise Http404()
        return super(TransferDomainView, self).dispatch(request, *args, **kwargs)


class ActivateTransferDomainView(BasePageView):
    urlname = 'activate_transfer_domain'
    page_title = 'Activate Domain Transfer'
    template_name = 'domain/activate_transfer_domain.html'

    @property
    @memoized
    def active_transfer(self):
        return TransferDomainRequest.get_by_guid(self.guid)

    @property
    def page_context(self):
        if self.active_transfer:
            return {'transfer': self.active_transfer.as_dict()}
        else:
            return {}

    @property
    def page_url(self):
        return self.request.get_full_path()

    def get(self, request, guid, *args, **kwargs):
        self.guid = guid

        if (self.active_transfer and
                self.active_transfer.to_username != request.user.username and
                not request.user.is_superuser):
            return HttpResponseRedirect(reverse("no_permissions"))

        return super(ActivateTransferDomainView, self).get(request, *args, **kwargs)

    def post(self, request, guid, *args, **kwargs):
        self.guid = guid

        if not self.active_transfer:
            raise Http404()

        if self.active_transfer.to_username != request.user.username and not request.user.is_superuser:
            return HttpResponseRedirect(reverse("no_permissions"))

        self.active_transfer.transfer_domain(ip=get_ip(request))
        messages.success(request, _("Successfully transferred ownership of project '{domain}'")
                         .format(domain=self.active_transfer.domain))

        return HttpResponseRedirect(reverse('dashboard_default', args=[self.active_transfer.domain]))

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(ActivateTransferDomainView, self).dispatch(*args, **kwargs)


class DeactivateTransferDomainView(View):

    def post(self, request, guid, *args, **kwargs):

        transfer = TransferDomainRequest.get_by_guid(guid)

        if not transfer:
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))

        if (transfer.to_username != request.user.username and
                transfer.from_username != request.user.username and
                not request.user.is_superuser):
            return HttpResponseRedirect(reverse("no_permissions"))

        transfer.active = False
        transfer.save()

        referer = request.META.get('HTTP_REFERER', '/')

        # Do not want to send them back to the activate page
        if referer.endswith(reverse('activate_transfer_domain', args=[guid])):
            messages.info(request,
                          _("Declined ownership of project '{domain}'").format(domain=transfer.domain))
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(referer)

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(DeactivateTransferDomainView, self).dispatch(*args, **kwargs)


class PasswordResetView(View):
    urlname = "password_reset_confirm"

    def get(self, request, *args, **kwargs):
        extra_context = kwargs.setdefault('extra_context', {})
        extra_context['hide_password_feedback'] = settings.ENABLE_DRACONIAN_SECURITY_FEATURES
        extra_context['implement_password_obfuscation'] = settings.OBFUSCATE_PASSWORD_FOR_NIC_COMPLIANCE
        return password_reset_confirm(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        extra_context = kwargs.setdefault('extra_context', {})
        extra_context['hide_password_feedback'] = settings.ENABLE_DRACONIAN_SECURITY_FEATURES
        response = password_reset_confirm(request, *args, **kwargs)
        uidb64 = kwargs.get('uidb64')
        uid = urlsafe_base64_decode(uidb64)
        user = User.objects.get(pk=uid)
        couch_user = CouchUser.from_django_user(user)
        clear_login_attempts(couch_user)
        return response


@method_decorator(domain_admin_required, name='dispatch')
class RecoveryMeasuresHistory(BaseAdminProjectSettingsView):
    urlname = 'recovery_measures_history'
    page_title = ugettext_lazy("Recovery Measures History")
    template_name = 'domain/admin/recovery_measures_history.html'

    @property
    def page_context(self):
        measures_by_app_id = defaultdict(list)
        for measure in (MobileRecoveryMeasure.objects
                        .filter(domain=self.domain)
                        .order_by('pk')):
            measures_by_app_id[measure.app_id].append(measure)

        all_apps = get_apps_in_domain(self.domain, include_remote=False)
        return {
            'measures_by_app': sorted((
                (app.name, measures_by_app_id[app._id])
                for app in all_apps
            ), key=lambda x: (-1 * len(x[1]), x[0])),
        }
