from django import forms
from django.db import transaction
from django.template.defaultfilters import slugify
from django.urls import reverse
from django.utils.translation import ugettext_lazy
from django.utils.translation import ugettext as _

from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy

from corehq.apps.accounting.models import BillingAccount
from corehq.apps.hqwebapp import crispy as hqcrispy
from crispy_forms import bootstrap as twbscrispy
from corehq.apps.hqwebapp.widgets import BootstrapCheckboxInput
from corehq.apps.sso.models import IdentityProvider
from corehq.apps.sso import utils


def _validate_or_raise_slugify_error(slug):
    slugified_test = slugify(slug)
    if slug != slugified_test:
        raise forms.ValidationError(
            _("You did not enter a valid slug. Did you mean '{}'?").format(
                slugified_test)
        )


class CreateIdentityProviderForm(forms.Form):
    """This form initializes the essential fields of an IdentityProvider
    """
    owner = forms.IntegerField(
        label=ugettext_lazy("Billing Account Owner"),
        widget=forms.Select(choices=[]),
    )
    name = forms.CharField(
        label=ugettext_lazy("Public Name"),
        help_text=ugettext_lazy(
            "Users will see this name when logging in."
        ),
        max_length=128,
    )
    slug = forms.CharField(
        label=ugettext_lazy("Slug for SP Endpoints"),
        help_text=ugettext_lazy(
            "This will be the unique slug for this IdP's SAML2 urls. "
        ),
        max_length=256,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Primary Configuration'),
                crispy.Field(
                    'owner',
                    css_class="input-xxlarge",
                    placeholder="Search for Billing Account"
                ),
                'name',
                'slug',
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    ugettext_lazy("Create Identity Provider"),
                    type="submit",
                    css_class="btn btn-primary",
                )
            )
        )

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        _validate_or_raise_slugify_error(slug)
        if IdentityProvider.objects.filter(slug=slug).exists():
            raise forms.ValidationError(
                _("A Identity Provider already exists with this slug.")
            )
        return slug

    @transaction.atomic
    def create_identity_provider(self, admin_user):
        owner = BillingAccount.objects.get(id=self.cleaned_data['owner'])
        idp = IdentityProvider.objects.create(
            owner=owner,
            slug=self.cleaned_data['slug'],
            name=self.cleaned_data['name'],
            created_by=admin_user.username,
            last_modified_by=admin_user.username,
        )
        idp.create_service_provider_certificate()
        return idp


class ServiceProviderDetailsForm(forms.Form):
    """This form is for display purposes and lists all the
    required service provider information that's needed to link with an
    identity provider."""
    sp_entity_id = forms.CharField(
        label=ugettext_lazy("Entity ID"),
        required=False,
    )
    sp_acs_url = forms.CharField(
        label=ugettext_lazy("Assertion Consumer Service"),
        required=False,
    )
    sp_logout_url = forms.CharField(
        label=ugettext_lazy("Logout URL"),
        required=False,
    )
    sp_public_cert = forms.CharField(
        label=ugettext_lazy("Public x509 Cert"),
        required=False,
    )
    sp_public_cert_expiration = forms.CharField(
        label=ugettext_lazy("Certificate Expires On"),
        required=False,
    )
    sp_rollover_cert = forms.CharField(
        label=ugettext_lazy("Rollover x509 Cert"),
        required=False,
    )

    def __init__(self, identity_provider, *args, **kwargs):
        self.idp = identity_provider
        # todo eventually have a setting for IdentityProvider toggles based on
        #  whether SP signing is enforced (dependent on client's Azure tier)
        self.show_public_cert = kwargs.pop('show_public_cert', True)
        self.show_rollover_cert = kwargs.pop('show_rollover_cert', True)
        self.show_help_block = kwargs.pop('show_help_block', True)

        super().__init__(*args, **kwargs)

    @property
    def service_provider_help_block(self):
        help_link = "#"  # todo
        help_text = _('<a href="{}">Please read this guide</a> on how to set up '
                      'CommCare HQ with Azure AD.<br />You will need the following '
                      'information:').format(help_link)
        return crispy.HTML(
            f'<p class="help-block">{help_text}</p>'
        )

    @property
    def service_provider_fields(self):
        download = _("Download")
        shown_fields = []
        if self.show_help_block:
            shown_fields.append(self.service_provider_help_block)
        shown_fields.extend([
            hqcrispy.B3TextField(
                'sp_entity_id',
                utils.get_saml_entity_id(self.idp),
            ),
            hqcrispy.B3TextField(
                'sp_acs_url',
                utils.get_saml_acs_url(self.idp),
            ),
            hqcrispy.B3TextField(
                'sp_logout_url',
                utils.get_saml_sls_url(self.idp),
            ),
        ])
        if self.show_public_cert:
            shown_fields.extend([
                hqcrispy.B3TextField(
                    'sp_public_cert',
                    f'<a href="?sp_cert_public" target="_blank">{download}</a>',
                ),
                hqcrispy.B3TextField(
                    'sp_public_cert_expiration',
                    self.idp.date_sp_cert_expiration.strftime(
                        '%d %B %Y at %H:%M UTC'
                    ),
                ),
            ])
        if self.show_rollover_cert:
            shown_fields.append(hqcrispy.B3TextField(
                'sp_rollover_cert',
                (f'<a href="?sp_rollover_cert_public" target="_blank">{download}</a>'
                    if self.idp.sp_rollover_cert_public
                    else _("Not needed/generated yet.")),
            ))
        return shown_fields


class EditIdentityProviderAdminForm(forms.Form):
    """This is the form used by Accounting admins to modify the IdentityProvider
    configuration
    """
    owner = forms.CharField(
        label=ugettext_lazy("Billing Account Owner"),
        required=False,
    )
    slug = forms.CharField(
        label=ugettext_lazy("Slug"),
        required=False,
        help_text=ugettext_lazy(
            "CAUTION: Changing this value will alter the SAML endpoint URLs "
            "below and affect active SSO setups for the client!"
        ),
    )
    name = forms.CharField(
        label=ugettext_lazy("Public Name"),
        max_length=128,
        help_text=ugettext_lazy(
            "This text is what users will see when logging in with SSO."
        )
    )
    is_editable = forms.BooleanField(
        label=ugettext_lazy("Enterprise Dashboard"),
        required=False,
        widget=BootstrapCheckboxInput(
            inline_label=ugettext_lazy(
                "Allow Enterprise Admins to edit SSO Enterprise Settings"
            ),
        ),
    )
    is_active = forms.BooleanField(
        label=ugettext_lazy("Active Status"),
        required=False,
        widget=BootstrapCheckboxInput(
            inline_label=ugettext_lazy(
                "Single Sign On is active"
            ),
        ),
        help_text=ugettext_lazy(
            "Force users with matching email domains to log in with SSO."
        ),
    )

    def __init__(self, identity_provider, *args, **kwargs):
        self.idp = identity_provider
        kwargs['initial'] = {
            'name': identity_provider.name,
            'is_editable': identity_provider.is_editable,
            'is_active': identity_provider.is_active,
            'slug': identity_provider.slug,
        }
        super().__init__(*args, **kwargs)

        sp_details_form = ServiceProviderDetailsForm(
            identity_provider, show_help_block=False
        )
        self.fields.update(sp_details_form.fields)

        from corehq.apps.accounting.views import ManageBillingAccountView
        account_link = reverse(
            ManageBillingAccountView.urlname,
            args=(identity_provider.owner.id,)
        )

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Div(
                    crispy.Fieldset(
                        _('Primary Configuration'),
                        hqcrispy.B3TextField(
                            'owner',
                            f'<a href="{account_link}">'
                            f'{identity_provider.owner.name}</a>'
                        ),
                        'name',
                        twbscrispy.PrependedText('is_editable', ''),
                        twbscrispy.PrependedText('is_active', ''),
                    ),
                    css_class="panel-body"
                ),
                css_class="panel panel-modern-gray panel-form-only"
            ),
            crispy.Div(
                crispy.Div(
                    crispy.Fieldset(
                        _('Service Provider Settings'),
                        'slug',
                        *sp_details_form.service_provider_fields
                    ),
                    css_class="panel-body"
                ),
                css_class="panel panel-modern-gray panel-form-only"
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    ugettext_lazy("Update Configuration"),
                    type="submit",
                    css_class="btn btn-primary",
                )
            )
        )

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        _validate_or_raise_slugify_error(slug)
        if IdentityProvider.objects.filter(slug=slug).exclude(id=self.idp.id).exists():
            raise forms.ValidationError(
                _("Another Identity Provider already exists with this slug.")
            )
        return slug

    @transaction.atomic
    def update_identity_provider(self, admin_user):
        self.idp.slug = self.cleaned_data['slug']
        self.idp.is_editable = self.cleaned_data['is_editable']
        self.idp.is_active = self.cleaned_data['is_active']
        self.idp.last_modified_by = admin_user.username
        self.idp.save()
        return self.idp
