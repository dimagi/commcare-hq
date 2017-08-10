from crispy_forms import layout as crispy
from crispy_forms import bootstrap as twbscrispy
from crispy_forms.helper import FormHelper
from crispy_forms.bootstrap import StrictButton, PrependedText
from django import forms
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _, ugettext_lazy
from corehq.apps.domain.models import Domain
from corehq.apps.style import crispy as hqcrispy
from corehq.toggles import LINKED_APPS


class CopyApplicationForm(forms.Form):
    domain = forms.CharField(
        label=ugettext_lazy("Copy this app to project"),
        widget=forms.TextInput(attrs={
            "data-bind": "autocompleteSelect2: domain_names",
        }))
    name = forms.CharField(required=True, label=ugettext_lazy('Name'))
    linked = forms.BooleanField(
        required=False,
        label=_('Copy as Linked Application'),
        help_text=_("This will create an application that can be updated from changes to this application.")
    )

    # Toggles to enable when copying the app
    toggles = forms.CharField(required=False, widget=forms.HiddenInput, max_length=5000)

    def __init__(self, from_domain, app, *args, **kwargs):
        export_zipped_apps_enabled = kwargs.pop('export_zipped_apps_enabled', False)
        super(CopyApplicationForm, self).__init__(*args, **kwargs)
        fields = ['domain', 'name', 'toggles']
        if app:
            self.fields['name'].initial = app.name
        if export_zipped_apps_enabled:
            self.fields['gzip'] = forms.FileField(required=False)
            fields.append('gzip')
        if LINKED_APPS.enabled(from_domain):
            fields.append(PrependedText('linked', ''))

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Copy Application'),
                *fields
            ),
            crispy.Hidden('app', app.get_id),
            hqcrispy.FormActions(
                StrictButton(_('Copy'), type='button', css_class='btn-primary')
            )
        )

    def clean_domain(self):
        domain_name = self.cleaned_data['domain']
        domain = Domain.get_by_name(domain_name)
        if domain is None:
            raise forms.ValidationError("A valid project space is required.")
        return domain_name

    def clean(self):
        domain = self.cleaned_data.get('domain')
        if self.cleaned_data.get('linked'):
            if not LINKED_APPS.enabled(domain):
                raise forms.ValidationError("The target project space does not have linked apps enabled.")


class PromptUpdateSettingsForm(forms.Form):
    app_prompt = forms.ChoiceField(
        label=ugettext_lazy("Prompt Updates to Latest Released App Version"),
        choices=(
            ('off', ugettext_lazy('Off')),
            ('on', ugettext_lazy('On')),
            ('forced', ugettext_lazy('Forced')),
        ),
        help_text=ugettext_lazy(
            "If enabled, users will receive in-app prompts to update "
            "to the latest released version of the app, if they are not "
            "already on it. (Selecting 'Forced' will make it so that users "
            "cannot continue to use CommCare until they update)"
        )
    )

    apk_prompt = forms.ChoiceField(
        label=ugettext_lazy("Prompt Updates to Latest CommCare Version"),
        choices=(
            ('off', ugettext_lazy('Off')),
            ('on', ugettext_lazy('On')),
            ('forced', ugettext_lazy('Forced')),
        ),
        help_text=ugettext_lazy(
            "If enabled, users will receive in-app prompts to update "
            "to the latest version of CommCare, if they are not already "
            "on it. (Selecting 'Forced' will make it so that users cannot "
            "continue to use CommCare until they upgrade)"
        )
    )

    def __init__(self, *args, **kwargs):
        domain = kwargs.pop('domain')
        app_id = kwargs.pop('app_id')
        super(PromptUpdateSettingsForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()

        self.helper.form_method = 'POST'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_action = reverse(
            'update_prompt_settings',
            args=[domain, app_id])

        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_text_inline = True

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Manage Update Settings"),
                crispy.Field('app_prompt'),
                crispy.Field('apk_prompt'),
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Save"),
                    type="submit",
                    css_class="btn btn-success",
                )
            ),
        )

    @classmethod
    def from_app(cls, app):
        if app.is_remote_app() or not app.enable_update_prompts:
            return None
        app_config = app.global_app_config
        return cls(domain=app.domain, app_id=app.id, initial={
            'app_prompt': app_config.app_prompt,
            'apk_prompt': app_config.apk_prompt,
        })
