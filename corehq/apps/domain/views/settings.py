import pytz
import json
from collections import defaultdict
from functools import cached_property

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordResetConfirmView
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST

from couchdbkit import ResourceNotFound
from django_prbac.decorators import requires_privilege_raise404
from django_prbac.utils import has_privilege
from memoized import memoized

from corehq.apps.accounting.decorators import always_allow_project_access
from corehq.apps.enterprise.mixins import ManageMobileWorkersMixin
from dimagi.utils.web import json_response

from corehq import feature_previews, privileges, toggles
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.case_search.models import (
    CaseSearchConfig,
    FuzzyProperties,
    IgnorePatterns,
    case_search_synchronous_web_apps_for_domain,
    disable_case_search,
    enable_case_search, case_search_sync_cases_on_form_entry_enabled_for_domain,
)
from corehq.apps.domain.decorators import (
    domain_admin_required,
    login_and_domain_required,
    LoginAndDomainMixin,
)
from corehq.apps.domain.extension_points import has_custom_clean_password
from corehq.apps.domain.forms import (
    USE_LOCATION_CHOICE,
    USE_PARENT_LOCATION_CHOICE,
    DomainAlertForm,
    DomainGlobalSettingsForm,
    DomainMetadataForm,
    PrivacySecurityForm,
    ProjectSettingsForm,
    clean_password
)
from corehq.apps.domain.models import Domain
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqwebapp.models import Alert
from corehq.apps.hqwebapp.signals import clear_login_attempts
from corehq.apps.locations.permissions import location_safe
from corehq.apps.ota.models import MobileRecoveryMeasure
from corehq.apps.users.decorators import require_can_manage_domain_alerts
from corehq.apps.users.models import CouchUser
from corehq.toggles import NAMESPACE_DOMAIN
from corehq.toggles.models import Toggle
from corehq.util.timezones.conversions import UserTime, ServerTime

MAX_ACTIVE_ALERTS = 3


class BaseProjectSettingsView(BaseDomainView):
    section_name = gettext_lazy("Project Settings")
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
        return reverse(DefaultProjectSettingsView.urlname, args=[self.domain])


@method_decorator(always_allow_project_access, name='dispatch')
class DefaultProjectSettingsView(BaseDomainView):
    urlname = 'domain_settings_default'

    def get(self, request, *args, **kwargs):
        if request.couch_user.is_domain_admin(self.domain) and has_privilege(request, privileges.PROJECT_ACCESS):
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
            'cloudcare_releases': self.domain_object.cloudcare_releases,
        })
        return context


class EditBasicProjectInfoView(BaseEditProjectInfoView):
    template_name = 'domain/admin/info_basic.html'
    urlname = 'domain_basic_info'
    page_title = gettext_lazy("Basic")

    @method_decorator(domain_admin_required)
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
            'default_geocoder_location': self.domain_object.default_geocoder_location,
            'case_sharing': json.dumps(self.domain_object.case_sharing),
            'call_center_enabled': self.domain_object.call_center_config.enabled,
            'call_center_type': self.initial_call_center_type,
            'call_center_case_owner': self.initial_call_center_case_owner,
            'call_center_case_type': self.domain_object.call_center_config.case_type,
            'commtrack_enabled': self.domain_object.commtrack_enabled,
            'mobile_ucr_sync_interval': self.domain_object.default_mobile_ucr_sync_interval,
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
            'mapbox_access_token': settings.MAPBOX_ACCESS_TOKEN
        }

    def post(self, request, *args, **kwargs):
        if self.basic_info_form.is_valid():
            if self.basic_info_form.save(request, self.domain_object):
                messages.success(request, _("Project settings saved!"))
            else:
                messages.error(request, _("There was an error saving your settings. Please try again!"))
            return HttpResponseRedirect(self.page_url)

        return self.get(request, *args, **kwargs)


class EditMyProjectSettingsView(BaseProjectSettingsView):
    template_name = 'domain/admin/my_project_settings.html'
    urlname = 'my_project_settings'
    page_title = gettext_lazy("My Timezone")

    @method_decorator(always_allow_project_access)
    @method_decorator(login_and_domain_required)
    def dispatch(self, *args, **kwargs):
        return super(LoginAndDomainMixin, self).dispatch(*args, **kwargs)

    @property
    @memoized
    def my_project_settings_form(self):
        initial = {'global_timezone': self.domain_object.default_timezone}
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


@location_safe
def logo(request, domain):
    logo = Domain.get_by_name(domain).get_custom_logo()
    if logo is None:
        raise Http404()

    return HttpResponse(logo[0], content_type=logo[1])


class EditPrivacySecurityView(BaseAdminProjectSettingsView):
    template_name = "domain/admin/project_privacy.html"
    urlname = "privacy_info"
    page_title = gettext_lazy("Privacy and Security")

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseProjectSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def privacy_form(self):
        initial = {
            "secure_submissions": self.domain_object.secure_submissions,
            "secure_sessions_timeout": self.domain_object.secure_sessions_timeout,
            "restrict_superusers": self.domain_object.restrict_superusers,
            "allow_domain_requests": self.domain_object.allow_domain_requests,
            "hipaa_compliant": self.domain_object.hipaa_compliant,
            "secure_sessions": self.domain_object.secure_sessions,
            "two_factor_auth": self.domain_object.two_factor_auth,
            "strong_mobile_passwords": self.domain_object.strong_mobile_passwords,
            "ga_opt_out": self.domain_object.ga_opt_out,
            "disable_mobile_login_lockout": self.domain_object.disable_mobile_login_lockout,
            "allow_invite_email_only": self.domain_object.allow_invite_email_only,
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
            return redirect(self.urlname, domain=self.domain)
        return self.get(request, *args, **kwargs)


class CaseSearchConfigView(BaseAdminProjectSettingsView):
    urlname = 'case_search_config'
    page_title = gettext_lazy('Case Search')
    template_name = 'domain/admin/case_search.html'

    @method_decorator(domain_admin_required)
    @method_decorator(toggles.SYNC_SEARCH_CASE_CLAIM.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(CaseSearchConfigView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        request_json = json.loads(request.body.decode('utf-8'))
        enable = request_json.get('enable')
        fuzzies_by_casetype = request_json.get('fuzzy_properties')
        updated_fuzzies = []
        for case_type, properties in fuzzies_by_casetype.items():
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

        config, _ = CaseSearchConfig.objects.update_or_create(domain=self.domain, defaults={
            'enabled': request_json.get('enable'),
            'synchronous_web_apps': request_json.get('synchronous_web_apps'),
            'sync_cases_on_form_entry': request_json.get('sync_cases_on_form_entry'),
        })
        case_search_synchronous_web_apps_for_domain.clear(self.domain)
        case_search_sync_cases_on_form_entry_enabled_for_domain.clear(self.domain)
        config.ignore_patterns.set(updated_ignore_patterns)
        config.fuzzy_properties.set(updated_fuzzies)
        return json_response(self.page_context)

    @property
    def page_context(self):
        apps = get_apps_in_domain(self.domain, include_remote=False)
        case_types = {t for app in apps for t in app.get_case_types() if t}
        config = CaseSearchConfig.objects.get_or_none(pk=self.domain) or CaseSearchConfig(domain=self.domain)
        return {
            'case_types': sorted(list(case_types)),
            'case_search_url': reverse("case_search", args=[self.domain]),
            'values': {
                'enabled': config.enabled,
                'synchronous_web_apps': config.synchronous_web_apps,
                'sync_cases_on_form_entry': config.sync_cases_on_form_entry,
                'fuzzy_properties': {
                    fp.case_type: fp.properties for fp in config.fuzzy_properties.all()
                },
                'ignore_patterns': [{
                    'case_type': rc.case_type,
                    'case_property': rc.case_property,
                    'regex': rc.regex
                } for rc in config.ignore_patterns.all()]
            }
        }


class FeaturePreviewsView(BaseAdminProjectSettingsView):
    urlname = 'feature_previews'
    page_title = gettext_lazy("Feature Previews")
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
        if slug not in [f.slug for f, _ in self.features()]:
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
        feature_previews.previews_enabled_for_domain.clear(self.domain)

        return redirect('feature_previews', domain=self.domain)

    def update_feature(self, feature, current_state, new_state):
        if current_state != new_state:
            feature.set(self.domain, new_state, NAMESPACE_DOMAIN)
            if feature.save_fn is not None:
                feature.save_fn(self.domain, new_state)


class CustomPasswordResetView(PasswordResetConfirmView):
    urlname = "password_reset_confirm"

    def get_success_url(self):
        if self.user:
            # redirect mobile worker password reset to a domain-specific login with their username already set
            couch_user = CouchUser.get_by_username(self.user.username)
            if couch_user.is_commcare_user():
                messages.success(
                    self.request,
                    _('Password for {} has successfully been reset. You can now login.').format(
                        couch_user.raw_username
                    )
                )
                return '{}?username={}'.format(
                    reverse('domain_login', args=[couch_user.domain]),
                    couch_user.raw_username,
                )
        return super().get_success_url()

    def get(self, request, *args, **kwargs):

        self.extra_context['hide_password_feedback'] = has_custom_clean_password()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.extra_context['hide_password_feedback'] = has_custom_clean_password()
        if request.POST['new_password1'] == request.POST['new_password2']:
            try:
                clean_password(request.POST['new_password1'])
            except ValidationError as e:
                messages.error(request, _(e.message))
                return HttpResponseRedirect(request.path_info)
        response = super().post(request, *args, **kwargs)
        uidb64 = kwargs.get('uidb64')
        uid = urlsafe_base64_decode(uidb64)
        user = User.objects.get(pk=uid)
        couch_user = CouchUser.from_django_user(user)
        clear_login_attempts(couch_user)
        return response


@method_decorator(domain_admin_required, name='dispatch')
class RecoveryMeasuresHistory(BaseAdminProjectSettingsView):
    urlname = 'recovery_measures_history'
    page_title = gettext_lazy("Recovery Measures History")
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


class ManageDomainMobileWorkersView(ManageMobileWorkersMixin, BaseAdminProjectSettingsView):
    page_title = gettext_lazy("Manage Mobile Workers")
    template_name = 'enterprise/manage_mobile_workers.html'
    urlname = 'domain_manage_mobile_workers'


@method_decorator([requires_privilege_raise404(privileges.CUSTOM_DOMAIN_ALERTS),
                   require_can_manage_domain_alerts], name='dispatch')
class BaseDomainAlertsView(BaseProjectSettingsView):
    @staticmethod
    def _convert_user_time_to_server_time(timestamp, timezone):
        return UserTime(
            timestamp,
            tzinfo=pytz.timezone(timezone)
        ).server_time()

    @staticmethod
    def _convert_server_time_to_user_time(timestamp, timezone):
        return ServerTime(timestamp).user_time(pytz.timezone(timezone))


class ManageDomainAlertsView(BaseDomainAlertsView):
    template_name = 'domain/admin/manage_alerts.html'
    urlname = 'domain_manage_alerts'
    page_title = gettext_lazy("Manage Project Alerts")

    @property
    def page_context(self):
        return {
            'form': self.form,
            'alerts': [
                {
                    'start_time': (
                        self._convert_server_time_to_user_time(alert.start_time, alert.timezone).ui_string()
                        if alert.start_time else None
                    ),
                    'end_time': (
                        self._convert_server_time_to_user_time(alert.end_time, alert.timezone).ui_string()
                        if alert.end_time else None
                    ),
                    'active': alert.active,
                    'html': alert.html,
                    'id': alert.id,
                    'created_by_user': alert.created_by_user,
                }
                for alert in Alert.objects.filter(created_by_domain=self.domain)
            ]
        }

    @cached_property
    def form(self):
        if self.request.method == 'POST':
            return DomainAlertForm(self.request, self.request.POST)
        return DomainAlertForm(self.request)

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            self._create_alert()
            messages.success(request, _("Alert saved!"))
        else:
            messages.error(request, _("There was an error saving your alert. Please try again!"))
            return self.get(request, *args, **kwargs)
        return HttpResponseRedirect(self.page_url)

    def _create_alert(self):
        start_time = self.form.cleaned_data['start_time']
        end_time = self.form.cleaned_data['end_time']
        timezone = self.request.project.default_timezone

        start_time = (
            self._convert_user_time_to_server_time(start_time, timezone).done()
            if start_time else None
        )
        end_time = (
            self._convert_user_time_to_server_time(end_time, timezone).done()
            if end_time else None
        )

        Alert.objects.create(
            created_by_domain=self.domain,
            domains=[self.domain],
            text=self.form.cleaned_data['text'],
            start_time=start_time,
            end_time=end_time,
            timezone=timezone,
            created_by_user=self.request.couch_user.username,
        )


class EditDomainAlertView(BaseDomainAlertsView):
    template_name = 'domain/admin/edit_alert.html'
    urlname = 'domain_edit_alert'
    page_title = gettext_lazy("Edit Project Alert")

    @property
    @memoized
    def page_url(self):
        return reverse(ManageDomainAlertsView.urlname, args=[self.domain])

    @property
    def page_context(self):
        return {
            'form': self.form
        }

    @cached_property
    def form(self):
        if self.request.method == 'POST':
            return DomainAlertForm(self.request, self.request.POST)

        alert = self._get_alert()
        assert alert, "Alert not found"

        initial = {
            'text': alert.text,
            'start_time': (
                self._convert_server_time_to_user_time(alert.start_time, alert.timezone).done()
                if alert.start_time else None
            ),
            'end_time': (
                self._convert_server_time_to_user_time(alert.end_time, alert.timezone).done()
                if alert.end_time else None
            ),
        }
        return DomainAlertForm(self.request, initial=initial)

    def _get_alert(self):
        try:
            return Alert.objects.get(created_by_domain=self.domain, pk=self.kwargs.get('alert_id'))
        except Alert.DoesNotExist:
            return None

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            alert = self._get_alert()
            if not alert:
                messages.error(request, _("Alert not found!"))
            else:
                self._update_alert(alert)
                messages.success(request, _("Alert saved!"))
        else:
            messages.error(request, _("There was an error saving your alert. Please try again!"))
            return self.get(request, *args, **kwargs)
        return HttpResponseRedirect(self.page_url)

    def _update_alert(self, alert):
        alert.text = self.form.cleaned_data['text']

        start_time = self.form.cleaned_data['start_time']
        end_time = self.form.cleaned_data['end_time']
        timezone = self.request.project.default_timezone

        alert.start_time = (
            self._convert_user_time_to_server_time(start_time, timezone).done()
            if start_time else None
        )
        alert.end_time = (
            self._convert_user_time_to_server_time(end_time, timezone).done()
            if end_time else None
        )

        alert.save()


@require_POST
@requires_privilege_raise404(privileges.CUSTOM_DOMAIN_ALERTS)
@require_can_manage_domain_alerts
def update_domain_alert_status(request, domain):
    alert_id = request.POST.get('alert_id')
    assert alert_id, 'Missing alert ID'

    alert = _load_alert(alert_id, domain)
    if not alert:
        messages.error(request, _("Alert not found!"))
    else:
        _apply_update(request, alert)
    return HttpResponseRedirect(reverse(ManageDomainAlertsView.urlname, kwargs={'domain': domain}))


@require_POST
@requires_privilege_raise404(privileges.CUSTOM_DOMAIN_ALERTS)
@require_can_manage_domain_alerts
def delete_domain_alert(request, domain):
    alert_id = request.POST.get('alert_id')
    assert alert_id, 'Missing alert ID'
    alert = _load_alert(alert_id, domain)
    if not alert:
        messages.error(request, _("Alert not found!"))
    else:
        alert.delete()
        messages.success(request, _("Alert was removed!"))
    return HttpResponseRedirect(reverse(ManageDomainAlertsView.urlname, kwargs={'domain': domain}))


def _load_alert(alert_id, domain):
    try:
        return Alert.objects.get(
            created_by_domain=domain,
            id=alert_id
        )
    except Alert.DoesNotExist:
        return None


def _apply_update(request, alert):
    command = request.POST.get('command')
    if command == "activate":
        if Alert.objects.filter(created_by_domain=request.domain, active=True).count() >= MAX_ACTIVE_ALERTS:
            messages.error(request, _("Alert not activated. Only 3 active alerts allowed."))
            return

    if command in ['activate', 'deactivate']:
        _update_alert(alert, command)
        messages.success(request, _("Alert updated!"))
    else:
        messages.error(request, _("Unexpected update received. Alert not updated!"))


def _update_alert(alert, command):
    if command == 'activate':
        alert.active = True
    elif command == 'deactivate':
        alert.active = False
    alert.save()
