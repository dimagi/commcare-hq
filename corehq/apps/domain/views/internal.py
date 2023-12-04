import copy

from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_GET
from django.views.generic import View

from memoized import memoized

from corehq.apps.accounting.decorators import always_allow_project_access
from corehq.apps.domain.utils import log_domain_changes
from corehq.apps.ota.rate_limiter import restore_rate_limiter
from dimagi.utils.web import get_ip, json_request, json_response

from corehq import feature_previews, privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.domain.calculations import (
    CALC_FNS,
    CALC_ORDER,
    CALCS,
    dom_calc,
)
from corehq.apps.domain.decorators import (
    domain_admin_required,
    login_and_domain_required,
    login_required,
    require_superuser,
)
from corehq.apps.domain.forms import DomainInternalForm, TransferDomainForm
from corehq.apps.domain.models import Domain, TransferDomainRequest, AllowedUCRExpressionSettings
from corehq.apps.domain.views.settings import (
    BaseAdminProjectSettingsView,
    BaseProjectSettingsView,
)
from corehq.apps.hqwebapp.decorators import use_jquery_ui, use_multiselect, use_bootstrap5
from corehq.apps.hqwebapp.tasks import send_html_email_async, send_mail_async
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.receiverwrapper.rate_limiter import domain_case_rate_limiter, submission_rate_limiter
from corehq.apps.toggle_ui.views import ToggleEditView
from corehq.apps.users.models import CouchUser
from corehq.const import USER_CHANGE_VIA_WEB


class BaseInternalDomainSettingsView(BaseProjectSettingsView):
    strict_domain_fetching = True

    @method_decorator(always_allow_project_access)
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
        return format_html("{} <small>Internal</small>", self.page_title)


@method_decorator(use_bootstrap5, name='dispatch')
class TestBootstrap5DomainView(BaseInternalDomainSettingsView):
    urlname = 'test_bootstrap5_domain_view'
    page_title = gettext_lazy("Test Bootstrap 5 Changes")
    template_name = 'domain/test_bootstrap5.html'


class EditInternalDomainInfoView(BaseInternalDomainSettingsView):
    urlname = 'domain_internal_settings'
    page_title = gettext_lazy("Project Information")
    template_name = 'domain/internal_settings.html'
    strict_domain_fetching = True

    @method_decorator(always_allow_project_access)
    @method_decorator(login_and_domain_required)
    @method_decorator(require_superuser)
    @use_jquery_ui  # datepicker
    @use_multiselect
    def dispatch(self, request, *args, **kwargs):
        return super(BaseInternalDomainSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def internal_settings_form(self):
        can_edit_eula = toggles.CAN_EDIT_EULA.enabled(self.request.couch_user.username)
        if self.request.method == 'POST':
            return DomainInternalForm(self.request.domain, can_edit_eula, self.request.POST)
        initial = {
            'countries': self.domain_object.deployment.countries,
            'is_test': self.domain_object.is_test,
            'use_custom_auto_case_update_hour': 'Y' if self.domain_object.auto_case_update_hour else 'N',
            'auto_case_update_hour': self.domain_object.auto_case_update_hour,
            'use_custom_auto_case_update_limit': 'Y' if self.domain_object.auto_case_update_limit else 'N',
            'auto_case_update_limit': self.domain_object.auto_case_update_limit,
            'use_custom_odata_feed_limit': 'Y' if self.domain_object.odata_feed_limit else 'N',
            'odata_feed_limit': self.domain_object.odata_feed_limit,
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
        initial['active_ucr_expressions'] = AllowedUCRExpressionSettings.get_allowed_ucr_expressions(
            domain_name=self.domain_object.name
        )
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
            old_ucr_permissions = AllowedUCRExpressionSettings.get_allowed_ucr_expressions(self.domain)
            self.internal_settings_form.save(self.domain_object)
            log_domain_changes(
                self.request.couch_user.username,
                self.domain,
                self.internal_settings_form.cleaned_data['active_ucr_expressions'],
                old_ucr_permissions,
            )
            eula_props_changed = (
                bool(old_attrs.custom_eula) != bool(self.domain_object.internal.custom_eula)
                or bool(old_attrs.can_use_data) != bool(self.domain_object.internal.can_use_data)
            )

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
                    message, [settings.EULA_CHANGE_EMAIL]
                )

            messages.success(request,
                             _("The internal information for project %s was successfully updated!") % self.domain)
            if self.internal_settings_form.cleaned_data['send_handoff_email']:
                self.send_handoff_email()
            return redirect(self.urlname, self.domain)
        else:
            messages.error(request, _(
                "Your settings are not valid, see below for errors. Correct them and try again!"))
            return self.get(request, *args, **kwargs)


class EditInternalCalculationsView(BaseInternalDomainSettingsView):
    urlname = 'domain_internal_calculations'
    page_title = gettext_lazy("Calculated Properties")
    template_name = 'domain/internal_calculations.html'

    @method_decorator(always_allow_project_access)
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


@method_decorator(always_allow_project_access, name='dispatch')
@method_decorator(require_superuser, name='dispatch')
class FlagsAndPrivilegesView(BaseAdminProjectSettingsView):
    urlname = 'feature_flags_and_privileges'
    page_title = gettext_lazy("Feature Flags and Privileges")
    template_name = 'domain/admin/flags_and_privileges.html'

    def _get_toggles(self):

        def _sort_key(toggle):
            return (not (toggle['domain_enabled'] or toggle['user_enabled']),
                    toggle['tag_index'],
                    toggle['label'])

        unsorted_toggles = [{
            'slug': toggle.slug,
            'label': toggle.label,
            'description': toggle.description,
            'help_link': toggle.help_link,
            'tag': toggle.tag.name,
            'tag_index': toggle.tag.index,
            'tag_description': toggle.tag.description,
            'tag_css_class': toggle.tag.css_class,
            'has_domain_namespace': toggles.NAMESPACE_DOMAIN in toggle.namespaces,
            'domain_enabled': toggle.enabled(self.domain, namespace=toggles.NAMESPACE_DOMAIN),
            'user_enabled': toggle.enabled(self.request.couch_user.username,
                                           namespace=toggles.NAMESPACE_USER),
        } for toggle in toggles.all_toggles()]

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
            'toggles': self._get_toggles(),
            'privileges': self._get_privileges(),
        }


@method_decorator(always_allow_project_access, name='dispatch')
@method_decorator(require_superuser, name='dispatch')
class ProjectLimitsView(BaseAdminProjectSettingsView):
    urlname = 'internal_project_limits_summary'
    page_title = gettext_lazy("Project Limits")
    template_name = 'domain/admin/project_limits.html'

    @property
    def page_context(self):
        return get_project_limits_context([
            ('Submission Rate Limits', submission_rate_limiter),
            ('Case Rate Limits', domain_case_rate_limiter),
            ('Restore Rate Limits', restore_rate_limiter),
        ], self.domain)


def get_project_limits_context(name_limiter_tuple_list, scope=None):
    return {
        'project_limits': [
            (name, _get_rate_limits(scope, rate_limiter))
            for (name, rate_limiter) in name_limiter_tuple_list
        ]
    }


def _get_rate_limits(scope, rate_limiter):
    return [
        {'key': scope + ' ' + rate_counter.key, 'current_usage': int(current_usage), 'limit': int(limit),
         'percent_usage': round(100 * current_usage / limit, 1)}
        for scope, limits in rate_limiter.iter_rates(scope)
        for rate_counter, current_usage, limit in limits
    ]


class TransferDomainView(BaseAdminProjectSettingsView):
    urlname = 'transfer_domain_view'
    page_title = gettext_lazy("Transfer Project")
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
        if not toggles.TRANSFER_DOMAIN.enabled(request.domain):
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

        if (self.active_transfer
                and self.active_transfer.to_username != request.user.username
                and not request.user.is_superuser):
            return HttpResponseRedirect(reverse("no_permissions"))

        return super(ActivateTransferDomainView, self).get(request, *args, **kwargs)

    def post(self, request, guid, *args, **kwargs):
        self.guid = guid

        if not self.active_transfer:
            raise Http404()

        if self.active_transfer.to_username != request.user.username and not request.user.is_superuser:
            return HttpResponseRedirect(reverse("no_permissions"))

        self.active_transfer.transfer_domain(by_user=request.couch_user, transfer_via=USER_CHANGE_VIA_WEB,
                                             ip=get_ip(request))
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

        if (transfer.to_username != request.user.username
                and transfer.from_username != request.user.username
                and not request.user.is_superuser):
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


@login_and_domain_required
@require_superuser
@require_GET
def toggle_diff(request, domain):
    params = json_request(request.GET)
    other_domain = params.get('domain')
    diff = []
    if Domain.get_by_name(other_domain):
        diff = [{
            'slug': t.slug,
            'label': t.label,
            'url': reverse(ToggleEditView.urlname, args=[t.slug]),
            'tag_name': _('Preview'),
            'tag_css_class': 'default',
            'tag_index': -1,
        } for t in feature_previews.all_previews() if _can_copy_toggle(t, request.domain, other_domain)]
        diff.extend([{
            'slug': t.slug,
            'label': t.label,
            'url': reverse(ToggleEditView.urlname, args=[t.slug]),
            'tag_name': t.tag.name,
            'tag_css_class': t.tag.css_class,
            'tag_index': t.tag.index,
        } for t in toggles.all_toggles() if _can_copy_toggle(t, request.domain, other_domain)])
        diff.sort(key=lambda x: (x['tag_index'], x['label']))
    return json_response(diff)


def _can_copy_toggle(toggle, domain, other_domain):
    return (
        toggle.enabled(domain, toggles.NAMESPACE_DOMAIN)
        and not toggle.enabled(other_domain, toggles.NAMESPACE_DOMAIN)
    )


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
