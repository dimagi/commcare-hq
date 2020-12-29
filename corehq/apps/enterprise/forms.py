from django import forms
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import PrependedText, StrictButton
from crispy_forms.helper import FormHelper

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.toggles import DEFAULT_EXPORT_SETTINGS
from corehq.apps.export.models.export_settings import ExportFileType


class EnterpriseSettingsForm(forms.Form):
    restrict_domain_creation = forms.BooleanField(
        label=ugettext_lazy("Restrict Project Space Creation"),
        required=False,
        help_text=ugettext_lazy("Do not allow current web users, other than enterprise admins, "
                                "to create new project spaces."),
    )
    restrict_signup = forms.BooleanField(
        label=ugettext_lazy("Restrict User Signups"),
        required=False,
        help_text=ugettext_lazy("<span data-bind='html: restrictSignupHelp'></span>"),
    )
    restrict_signup_message = forms.CharField(
        label="Signup Restriction Message",
        required=False,
        help_text=ugettext_lazy("Message to display to users who attempt to sign up for an account"),
        widget=forms.Textarea(attrs={'rows': 2, 'maxlength': 512}),
    )

    forms_filetype = forms.ChoiceField(
        label=ugettext_lazy("Default File Type"),
        required=False,
        initial=ExportFileType.EXCEL_2007_PLUS,
        choices=ExportFileType.CHOICES,
    )

    forms_auto_convert = forms.BooleanField(
        label=ugettext_lazy("Automatically convert dates and multimedia links for Excel"),
        required=False,
        help_text=ugettext_lazy("Leaving this checked will ensure dates appear in excel format. "
                                "Otherwise they will appear as a normal text format. This also allows "
                                "for hyperlinks to the multimedia captured by your form submission.")
    )

    forms_auto_format_cells = forms.BooleanField(
        label=ugettext_lazy("Automatically format cells for Excel 2007+"),
        required=False,
        help_text=ugettext_lazy("If this setting is not selected, your export will be in Excel's generic format. "
                                "If you enable this setting, Excel will format dates, integers, decimals, "
                                "boolean values (True/False), and currencies.")
    )

    forms_include_duplicates = forms.BooleanField(
        label=ugettext_lazy("Include duplicates and other unprocessed forms"),
        required=False,
    )

    forms_expand_checkbox = forms.BooleanField(
        label=ugettext_lazy("Expand checkbox questions"),
        required=False,
    )

    cases_filetype = forms.ChoiceField(
        label=ugettext_lazy("Default File Type"),
        required=False,
        initial=ExportFileType.EXCEL_2007_PLUS,
        choices=ExportFileType.CHOICES,
    )

    cases_auto_convert = forms.BooleanField(
        label=ugettext_lazy("Automatically convert dates and multimedia links for Excel"),
        required=False,
        help_text=ugettext_lazy("Leaving this checked will ensure dates appear in excel format. "
                                "Otherwise they will appear as a normal text format. This also allows "
                                "for hyperlinks to the multimedia captured by your form submission.")
    )

    odata_include_duplicates = forms.BooleanField(
        label=ugettext_lazy("Include duplicates and other unprocessed forms"),
        required=False,
    )

    odata_expand_checkbox = forms.BooleanField(
        label=ugettext_lazy("Expand checkbox questions"),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.pop('domain', None)
        self.account = kwargs.pop('account', None)
        self.export_settings = kwargs.pop('export_settings', None)
        kwargs['initial'] = {
            "restrict_domain_creation": self.account.restrict_domain_creation,
            "restrict_signup": self.account.restrict_signup,
            "restrict_signup_message": self.account.restrict_signup_message,
            "forms_filetype": self.export_settings.forms_filetype,
            "forms_auto_convert": self.export_settings.forms_auto_convert,
            "forms_auto_format_cells": self.export_settings.forms_auto_format_cells,
            "forms_include_duplicates": self.export_settings.forms_include_duplicates,
            "forms_expand_checkbox": self.export_settings.forms_expand_checkbox,
            "cases_filetype": self.export_settings.cases_filetype,
            "cases_auto_convert": self.export_settings.cases_auto_convert,
            "odata_include_duplicates": self.export_settings.odata_include_duplicates,
            "odata_expand_checkbox": self.export_settings.odata_expand_checkbox,
        }
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

        if DEFAULT_EXPORT_SETTINGS.enabled(self.domain):
            self.helper.layout.append(
                crispy.Fieldset(
                    _("Edit Default Export Settings"),
                    crispy.Div(
                        crispy.HTML('<h4 style="font-weight: bold;">Form Data Exports</h4>')
                    ),
                    crispy.Div(
                        crispy.Field('forms_filetype'),
                    ),
                    crispy.Div(
                        crispy.Field('forms_auto_convert'),
                    ),
                    crispy.Div(
                        crispy.Field('forms_auto_format_cells')
                    ),
                    crispy.Div(
                        crispy.Field('forms_include_duplicates')
                    ),
                    crispy.Div(
                        crispy.Field('forms_expand_checkbox')
                    ),
                    crispy.Div(
                        crispy.HTML('<h4 style="font-weight: bold;">Case Data Exports</h4>')
                    ),
                    crispy.Div(
                        crispy.Field('cases_filetype')
                    ),
                    crispy.Div(
                        crispy.Field('cases_auto_convert'),
                    ),
                    crispy.Div(
                        crispy.HTML('<h4 style="font-weight: bold;">OData Feeds</h4>')
                    ),
                    crispy.Div(
                        crispy.Field('odata_include_duplicates')
                    ),
                    crispy.Div(
                        crispy.Field('odata_expand_checkbox'),
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

    def save(self, account, export_settings):
        account.restrict_domain_creation = self.cleaned_data.get('restrict_domain_creation', False)
        account.restrict_signup = self.cleaned_data.get('restrict_signup', False)
        account.restrict_signup_message = self.cleaned_data.get('restrict_signup_message', '')
        account.save()
        # forms
        export_settings.forms_filetype = self.cleaned_data.get('forms_filetype', export_settings.forms_filetype)
        export_settings.forms_auto_convert = self.cleaned_data.get('forms_auto_convert',
                                                                   export_settings.forms_auto_convert)
        export_settings.forms_auto_format_cells = self.cleaned_data.get('forms_auto_format_cells',
                                                                        export_settings.forms_auto_format_cells)
        export_settings.forms_include_duplicates = self.cleaned_data.get('forms_include_duplicates',
                                                                         export_settings.forms_include_duplicates)
        export_settings.forms_expand_checkbox = self.cleaned_data.get('forms_expand_checkbox',
                                                                      export_settings.forms_expand_checkbox)
        # cases
        export_settings.cases_filetype = self.cleaned_data.get('cases_filetype',
                                                               export_settings.cases_filetype)
        export_settings.cases_auto_convert = self.cleaned_data.get('cases_auto_convert',
                                                                   export_settings.cases_auto_convert)
        # odata
        export_settings.odata_include_duplicates = \
            self.cleaned_data.get('odata_include_duplicates', export_settings.odata_include_duplicates)
        export_settings.odata_expand_checkbox = \
            self.cleaned_data.get('odata_expand_checkbox', export_settings.odata_expand_checkbox)
        export_settings.save()
        return True
