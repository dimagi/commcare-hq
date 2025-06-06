from django import forms
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import PrependedText, StrictButton
from crispy_forms.helper import FormHelper

from corehq.apps.app_manager.util import is_linked_app
from corehq.apps.builds.models import BuildSpec
from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.linked_domain.models import DomainLink

from .dbaccessors import get_all_built_app_ids_and_versions
from .models import LATEST_APK_VALUE, LATEST_APP_VALUE
from .util import get_commcare_builds
from ..hqwebapp.widgets import BootstrapCheckboxInput
from ..linked_domain.util import can_domain_access_linked_domains


class CopyApplicationForm(forms.Form):
    domain = forms.CharField(
        label=gettext_lazy("Copy this app to project"),
        widget=forms.Select(choices=[], attrs={
            "data-bind": "autocompleteSelect2: domainNames, event:{ change: domainChanged }",
        }))
    name = forms.CharField(required=True, label=gettext_lazy('Name'))
    linked = forms.BooleanField(
        required=False,
        label=_('Copy as Linked Application'),
        widget=BootstrapCheckboxInput(
            inline_label=mark_safe(_(
                "<!-- ko ifnot: shouldEnableLinkedAppOption -->"
                "The selected project space is either not yet linked to the current project space, or you do not"
                " have the correct permissions in the selected project space. "
                "<a href=\"https://confluence.dimagi.com/display/commcarepublic/Linked+Project+Spaces\" "
                "target=\"_blank\">Learn more</a> about Linked Project Spaces."
                "<!-- /ko -->"
            )),  # nosec: no user input
            attrs={"data-bind": "enable: shouldEnableLinkedAppOption, checked: isChecked"},
        ),
        help_text=_("This will create an application that can be updated from changes to this application."
                    " This requires your app to have at least one released version."),
    )
    build_id = forms.CharField(
        required=False,
        label=_('Copy version'),
        widget=forms.Select(choices=[], attrs={"class": "app-manager-version-dropdown",
                                               "placeholder": _("Current")}))

    def __init__(self, from_domain, app, *args, **kwargs):
        super(CopyApplicationForm, self).__init__(*args, **kwargs)
        fields = ['domain', 'name', 'build_id']
        self.from_domain = from_domain
        if app:
            self.fields['name'].initial = app.name
        if can_domain_access_linked_domains(self.from_domain) and not is_linked_app(app):
            fields.append(PrependedText('linked', ''))

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Copy Application for Editing') if is_linked_app(app) else _('Copy Application'),
                *fields
            ),
            crispy.Hidden('app', app.get_id),
            hqcrispy.FormActions(
                StrictButton(_('Copy'), type='button', css_class='btn-primary')
            )
        )

    def clean_domain(self):
        domain = self.cleaned_data['domain']
        domain_obj = Domain.get_by_name(domain)
        if domain_obj is None:
            raise forms.ValidationError("A valid project space is required.")
        return domain

    def clean(self):
        domain = self.cleaned_data.get('domain')
        if self.cleaned_data.get('linked'):
            if not can_domain_access_linked_domains(domain):
                raise forms.ValidationError("The target project space does not have this feature enabled.")
            link = DomainLink.objects.filter(linked_domain=domain)
            if link and link[0].master_domain != self.from_domain:
                raise forms.ValidationError(
                    "The target project space is already linked to a different domain")
        return self.cleaned_data


class PromptUpdateSettingsForm(forms.Form):
    app_prompt = forms.ChoiceField(
        label=gettext_lazy("Prompt Updates to App"),
        choices=(
            ('off', gettext_lazy('Off')),
            ('on', gettext_lazy('On')),
            ('forced', gettext_lazy('Forced')),
        ),
        help_text=gettext_lazy(
            "If enabled, users will receive in-app prompts to update "
            "to the selected version of the app, if they are not "
            "already on it. (Selecting 'Forced' will make it so that users "
            "cannot continue to use CommCare until they update)"
        )
    )

    apk_prompt = forms.ChoiceField(
        label=gettext_lazy("Prompt Updates to CommCare"),
        choices=(
            ('off', gettext_lazy('Off')),
            ('on', gettext_lazy('On')),
            ('forced', gettext_lazy('Forced')),
        ),
        help_text=gettext_lazy(
            "If enabled, users will receive in-app prompts to update "
            "to the selected version of CommCare, if they are not already "
            "on it. (Selecting 'Forced' will make it so that users cannot "
            "continue to use CommCare until they upgrade)"
        )
    )

    apk_version = forms.ChoiceField(
        label=gettext_lazy("CommCare Version")
    )
    app_version = forms.ChoiceField(
        label=gettext_lazy("Application Version")
    )

    def __init__(self, *args, **kwargs):
        domain = kwargs.pop('domain')
        app_id = kwargs.pop('app_id')
        request_user = kwargs.pop('request_user')
        super(PromptUpdateSettingsForm, self).__init__(*args, **kwargs)

        self.fields['apk_version'].choices = [(LATEST_APK_VALUE, 'Latest Released Build')] + [
            (build.to_string(), 'CommCare {}'.format(build.get_menu_item_label()))
            for build in get_commcare_builds(request_user)
        ]

        self.fields['app_version'].choices = [(LATEST_APP_VALUE, 'Latest Released Version')] + [
            (app.version, 'Version {}'.format(app.version))
            for app in get_all_built_app_ids_and_versions(domain, app_id)[-10:]
        ]

        self.helper = FormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_id = 'update-manager'
        self.helper.form_action = reverse(
            'update_prompt_settings',
            args=[domain, app_id])

        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_text_inline = True

        show_apk_version_select = kwargs.get('initial', {}).get('apk_prompt', 'off') != 'off'
        show_app_version_select = kwargs.get('initial', {}).get('app_prompt', 'off') != 'off'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Manage Update Settings"),
                crispy.Field(
                    'apk_prompt',
                    # hide 'apk_version' depending on whether app_prompt is off or not
                    onchange="document.getElementById('apk_version_id').style.display = "
                             "document.getElementById('id_apk_prompt').value === 'off' ? 'none': 'block'",
                ),
                crispy.Div(
                    'apk_version',
                    # initial show/hide value
                    style=('' if show_apk_version_select else "display: none;"), css_id="apk_version_id"),
                crispy.Field(
                    'app_prompt',
                    # hide 'app_version' depending on whether app_prompt is off or not
                    onchange="document.getElementById('app_version_id').style.display = "
                             "document.getElementById('id_app_prompt').value === 'off' ? 'none': 'block'",
                ),
                crispy.Div(
                    'app_version',
                    # initial show/hide value
                    style=('' if show_app_version_select else "display: none;"), css_id="app_version_id"),
            )
        )

    @classmethod
    def from_app(cls, app, request_user):
        if app.is_remote_app() or not app.enable_update_prompts:
            return None
        app_config = app.global_app_config
        return cls(domain=app.domain, app_id=app.id, request_user=request_user, initial={
            'app_prompt': app_config.app_prompt,
            'apk_prompt': app_config.apk_prompt,
            'apk_version': app_config.apk_version,
            'app_version': app_config.app_version,
        })

    def clean_apk_version(self):
        # make sure it points to a valid BuildSpec
        apk_version = self.cleaned_data['apk_version']
        if apk_version == LATEST_APK_VALUE:
            return apk_version
        try:
            BuildSpec.from_string(apk_version)
            return apk_version
        except ValueError:
            raise forms.ValidationError(
                _('Invalid APK version %(version)s'), params={'version': apk_version})

    def clean_app_version(self):
        app_version = self.cleaned_data['app_version']
        try:
            return int(app_version)
        except ValueError:
            raise forms.ValidationError(
                _('Invalid app version %(version)s'), params={'version': app_version})
