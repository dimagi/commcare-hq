from __future__ import absolute_import, unicode_literals
from collections import defaultdict
import json

from couchdbkit import ResourceNotFound
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import View
from django.conf import settings
from django.utils.decorators import method_decorator
from django.utils.http import urlsafe_base64_decode
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.views import password_reset_confirm
from django.utils.translation import ugettext as _, ugettext_lazy
from django.contrib.auth.models import User

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.case_search.models import (
    CaseSearchConfig,
    FuzzyProperties,
    IgnorePatterns,
    enable_case_search,
    disable_case_search,
)
from corehq.apps.locations.permissions import location_safe
from corehq.apps.users.models import CouchUser
from corehq.toggles import NAMESPACE_DOMAIN
from custom.openclinica.forms import OpenClinicaSettingsForm
from custom.openclinica.models import OpenClinicaSettings
from dimagi.utils.couch.resource_conflict import retry_resource
from corehq import privileges, feature_previews
from django_prbac.utils import has_privilege
from corehq.apps.domain.decorators import domain_admin_required, login_and_domain_required
from corehq.apps.domain.forms import (
    DomainGlobalSettingsForm, DomainMetadataForm, PrivacySecurityForm,
    USE_PARENT_LOCATION_CHOICE, USE_LOCATION_CHOICE,
)
from corehq.apps.domain.models import Domain, LICENSES
from corehq.apps.domain.forms import ProjectSettingsForm
from corehq.apps.domain.views.base import BaseDomainView, LoginAndDomainMixin
from memoized import memoized
from dimagi.utils.web import json_response

from toggle.models import Toggle
from corehq.apps.hqwebapp.signals import clear_login_attempts
from corehq.apps.ota.models import MobileRecoveryMeasure
import six


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
            'cloudcare_releases': self.domain_object.cloudcare_releases,
        })
        return context


class EditBasicProjectInfoView(BaseEditProjectInfoView):
    template_name = 'domain/admin/info_basic.html'
    urlname = 'domain_basic_info'
    page_title = ugettext_lazy("Basic")

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
                messages.error(request, _("There was an error saving your settings. Please try again!"))
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
        request_json = json.loads(request.body.decode('utf-8'))
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
        feature_previews.previews_dict.clear(self.domain)

        return redirect('feature_previews', domain=self.domain)

    def update_feature(self, feature, current_state, new_state):
        if current_state != new_state:
            feature.set(self.domain, new_state, NAMESPACE_DOMAIN)
            if feature.save_fn is not None:
                feature.save_fn(self.domain, new_state)


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
