from django import forms
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import PrependedText, StrictButton
from crispy_forms.helper import FormHelper

from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.widgets import BootstrapCheckboxInput
from corehq.apps.export.models.export_settings import ExportFileType
from corehq.privileges import DEFAULT_EXPORT_SETTINGS


class EnterpriseSettingsForm(forms.Form):
    restrict_domain_creation = forms.BooleanField(
        label=gettext_lazy("Restrict Project Space Creation"),
        required=False,
        help_text=gettext_lazy("Do not allow current web users, other than enterprise admins, "
                               "to create new project spaces."),
    )
    restrict_signup = forms.BooleanField(
        label=gettext_lazy("Restrict User Signups"),
        required=False,
        help_text=gettext_lazy("<span data-bind='html: restrictSignupHelp'></span>"),
    )
    restrict_signup_message = forms.CharField(
        label="Signup Restriction Message",
        required=False,
        help_text=gettext_lazy("Message to display to users who attempt to sign up for an account"),
        widget=forms.Textarea(attrs={'rows': 2, 'maxlength': 512, "class": "vertical-resize"}),
    )

    forms_filetype = forms.ChoiceField(
        label=gettext_lazy("Default File Type"),
        required=False,
        initial=ExportFileType.EXCEL_2007_PLUS,
        choices=ExportFileType.CHOICES,
    )

    forms_auto_convert = forms.BooleanField(
        label=gettext_lazy("Excel Date & Multimedia Format"),
        widget=BootstrapCheckboxInput(
            inline_label=gettext_lazy(
                "Automatically convert dates and multimedia links for Excel"
            ),
        ),
        required=False,
        help_text=gettext_lazy("Leaving this checked will ensure dates appear in excel format. "
                               "Otherwise they will appear as a normal text format. This also allows "
                               "for hyperlinks to the multimedia captured by your form submission.")
    )

    forms_auto_format_cells = forms.BooleanField(
        label=gettext_lazy("Excel Cell Format"),
        widget=BootstrapCheckboxInput(
            inline_label=gettext_lazy(
                "Automatically format cells for Excel 2007+"
            ),
        ),
        required=False,
        help_text=gettext_lazy("If this setting is not selected, your export will be in Excel's generic format. "
                               "If you enable this setting, Excel will format dates, integers, decimals, "
                               "boolean values (True/False), and currencies.")
    )

    forms_expand_checkbox = forms.BooleanField(
        label=gettext_lazy("Checkbox Format"),
        widget=BootstrapCheckboxInput(
            inline_label=gettext_lazy(
                "Expand checkbox questions"
            ),
        ),
        required=False,
    )

    cases_filetype = forms.ChoiceField(
        label=gettext_lazy("Default File Type"),
        required=False,
        initial=ExportFileType.EXCEL_2007_PLUS,
        choices=ExportFileType.CHOICES,
    )

    cases_auto_convert = forms.BooleanField(
        label=gettext_lazy("Excel Date & Multimedia Format"),
        widget=BootstrapCheckboxInput(
            inline_label=gettext_lazy(
                "Automatically convert dates and multimedia links for Excel"
            ),
        ),
        required=False,
        help_text=gettext_lazy("Leaving this checked will ensure dates appear in excel format. "
                               "Otherwise they will appear as a normal text format. This also allows "
                               "for hyperlinks to the multimedia captured by your form submission.")
    )

    odata_expand_checkbox = forms.BooleanField(
        label=gettext_lazy("Checkbox Format"),
        widget=BootstrapCheckboxInput(
            inline_label=gettext_lazy(
                "Expand checkbox questions"
            ),
        ),
        help_text=gettext_lazy("Only applies to form exports."),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.pop('domain', None)
        self.account = kwargs.pop('account', None)
        self.username = kwargs.pop('username', None)
        self.export_settings = kwargs.pop('export_settings', None)
        kwargs['initial'] = {
            "restrict_domain_creation": self.account.restrict_domain_creation,
            "restrict_signup": self.account.restrict_signup,
            "restrict_signup_message": self.account.restrict_signup_message,
        }

        if self.export_settings and domain_has_privilege(self.domain, DEFAULT_EXPORT_SETTINGS):
            kwargs['initial'].update(self.export_settings.as_dict())

        super(EnterpriseSettingsForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_id = 'enterprise-settings-form'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_action = reverse("edit_enterprise_settings", args=[self.domain])
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Edit Enterprise Settings"),
                PrependedText('restrict_domain_creation', ''),
                crispy.Div(
                    PrependedText('restrict_signup', '', data_bind='checked: restrictSignup'),
                ),
                crispy.Div(
                    crispy.Field('restrict_signup_message'),
                    data_bind='visible: restrictSignup',
                ),
            )
        )

        if domain_has_privilege(self.domain, DEFAULT_EXPORT_SETTINGS):
            self.helper.layout.append(
                crispy.Div(
                    crispy.Fieldset(
                        _("Edit Default Form Export Settings"),
                        crispy.Div(
                            crispy.Field('forms_filetype'),
                        ),
                        PrependedText('forms_auto_convert', ''),
                        PrependedText('forms_auto_format_cells', ''),
                        PrependedText('forms_expand_checkbox', ''),
                    ),
                    crispy.Fieldset(
                        _("Edit Default Case Export Settings"),
                        crispy.Div(
                            crispy.Field('cases_filetype')
                        ),
                        PrependedText('cases_auto_convert', ''),
                    ),
                    crispy.Fieldset(
                        _("Edit Default OData Export Settings"),
                        PrependedText('odata_expand_checkbox', ''),
                    ),
                )
            )

        self.helper.layout.append(
            hqcrispy.FormActions(
                StrictButton(
                    _("Update Enterprise Settings"),
                    type="submit",
                    css_class='btn-primary',
                )
            )
        )

    def clean_restrict_signup_message(self):
        message = self.cleaned_data['restrict_signup_message']
        if self.cleaned_data['restrict_signup'] and not message:
            raise ValidationError(_("If restricting signups, a message is required."))
        return message

    def save(self, account):
        account.restrict_domain_creation = self.cleaned_data.get('restrict_domain_creation', False)
        account.restrict_signup = self.cleaned_data.get('restrict_signup', False)
        account.restrict_signup_message = self.cleaned_data.get('restrict_signup_message', '')
        account.save()

        if self.export_settings and domain_has_privilege(self.domain, DEFAULT_EXPORT_SETTINGS):
            # forms
            self.export_settings.forms_filetype = self.cleaned_data.get(
                'forms_filetype',
                self.export_settings.forms_filetype
            )
            self.export_settings.forms_auto_convert = self.cleaned_data.get(
                'forms_auto_convert',
                self.export_settings.forms_auto_convert
            )
            self.export_settings.forms_auto_format_cells = self.cleaned_data.get(
                'forms_auto_format_cells',
                self.export_settings.forms_auto_format_cells
            )
            self.export_settings.forms_expand_checkbox = self.cleaned_data.get(
                'forms_expand_checkbox',
                self.export_settings.forms_expand_checkbox
            )
            # cases
            self.export_settings.cases_filetype = self.cleaned_data.get(
                'cases_filetype',
                self.export_settings.cases_filetype
            )
            self.export_settings.cases_auto_convert = self.cleaned_data.get(
                'cases_auto_convert',
                self.export_settings.cases_auto_convert
            )
            # odata
            self.export_settings.odata_expand_checkbox = self.cleaned_data.get(
                'odata_expand_checkbox',
                self.export_settings.odata_expand_checkbox
            )
            self.export_settings.save()
        return True


class EnterpriseManageMobileWorkersForm(forms.Form):
    enable_auto_deactivation = forms.BooleanField(
        label=gettext_lazy("Auto-Deactivation by Inactivity"),
        widget=BootstrapCheckboxInput(
            inline_label=gettext_lazy(
                "Automatically deactivate Mobile Workers who have not "
                "submitted a form within the Inactivity Period below."
            ),
        ),
        required=False,
    )
    inactivity_period = forms.ChoiceField(
        label=gettext_lazy("Inactivity Period"),
        required=False,
        initial=90,
        choices=(
            (30, gettext_lazy("30 days")),
            (60, gettext_lazy("60 days")),
            (90, gettext_lazy("90 days")),
            (120, gettext_lazy("120 days")),
            (150, gettext_lazy("150 days")),
            (180, gettext_lazy("180 days")),
            (365, gettext_lazy("365 days")),
        ),
        help_text=gettext_lazy(
            "Mobile workers who have not submitted a form after these many "
            "days will be considered inactive."
        ),
    )
    allow_custom_deactivation = forms.BooleanField(
        label=gettext_lazy("Auto-Deactivation by Month"),
        required=False,
        widget=BootstrapCheckboxInput(
            inline_label=gettext_lazy(
                "Allow auto-deactivation of Mobile Workers after "
                "a specific month."
            ),
        ),
        help_text=gettext_lazy(
            "When this is enabled, an option to select a month and "
            "year for deactivating a Mobile Worker will be present when "
            "creating that Mobile Worker."
        ),
    )

    def __init__(self, *args, **kwargs):
        self.emw_settings = kwargs.pop('emw_settings', None)
        self.domain = kwargs.pop('domain', None)
        kwargs['initial'] = {
            "enable_auto_deactivation": self.emw_settings.enable_auto_deactivation,
            "inactivity_period": self.emw_settings.inactivity_period,
            "allow_custom_deactivation": self.emw_settings.allow_custom_deactivation,
        }

        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_id = 'emw-settings-form'
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Manage Mobile Workers"),
                PrependedText('enable_auto_deactivation', ''),
                crispy.Div(
                    crispy.Field('inactivity_period'),
                ),
                PrependedText('allow_custom_deactivation', ''),
            ),
            hqcrispy.FormActions(
                StrictButton(
                    _("Update Settings"),
                    type="submit",
                    css_class='btn-primary',
                )
            )
        )

    def update_settings(self):
        self.emw_settings.enable_auto_deactivation = self.cleaned_data['enable_auto_deactivation']
        self.emw_settings.inactivity_period = self.cleaned_data['inactivity_period']
        self.emw_settings.allow_custom_deactivation = self.cleaned_data['allow_custom_deactivation']
        self.emw_settings.save()
        for domain in self.emw_settings.account.get_domains():
            self.emw_settings.clear_domain_caches(domain)
