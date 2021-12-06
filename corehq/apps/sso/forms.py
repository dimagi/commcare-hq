import datetime
import logging

from django import forms
from django.db import transaction
from django.template.defaultfilters import slugify
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy
from django.utils.translation import ugettext as _

from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy

from corehq.apps.accounting.models import BillingAccount
from corehq.apps.hqwebapp import crispy as hqcrispy
from crispy_forms import bootstrap as twbscrispy
from corehq.apps.hqwebapp.widgets import BootstrapCheckboxInput
from corehq.apps.sso import certificates
from corehq.apps.sso.models import IdentityProvider
from corehq.apps.sso.utils import url_helpers
from corehq.apps.sso.utils.url_helpers import get_documentation_url

log = logging.getLogger(__name__)

TIME_FORMAT = "%Y/%m/%d %I:%M %p"


def _validate_or_raise_slugify_error(slug):
    slugified_test = slugify(slug)
    if slug != slugified_test:
        raise forms.ValidationError(
            _("You did not enter a valid slug. Did you mean '{}'?").format(
                slugified_test)
        )


def _check_is_editable_requirements(identity_provider):
    if not identity_provider.get_email_domains():
        raise forms.ValidationError(
            _("Please make sure you specify at "
              "least one Authenticated Email Domain.")
        )
    if not identity_provider.get_sso_exempt_users():
        raise forms.ValidationError(
            _("Please make sure you have specified at least one "
              "enterprise admin that is exempt from SSO.")
        )


def _check_required_when_active(is_active, value):
    if is_active and not value:
        raise forms.ValidationError(
            _("This is required when Single Sign On is active.")
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
        label=ugettext_lazy("Identifier (Entity ID)"),
        required=False,
    )
    sp_acs_url = forms.CharField(
        label=ugettext_lazy("Reply URL (Assertion Consumer Service)"),
        required=False,
    )
    sp_sign_on_url = forms.CharField(
        label=ugettext_lazy("Sign on URL"),
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

    def __init__(self, identity_provider, show_help_block=True, *args, **kwargs):
        self.idp = identity_provider
        # todo eventually have a setting for IdentityProvider toggles based on
        #  whether SP signing is enforced (dependent on client's Azure tier)
        self.show_help_block = show_help_block

        super().__init__(*args, **kwargs)

    @property
    def service_provider_help_block(self):
        help_link = get_documentation_url(self.idp)
        help_text = format_html(
            _('<a href="{}">Please read this guide</a> on how to set up '
              'CommCare HQ with Azure AD.<br />You will need the following '
              'information:'),
            help_link
        )
        return crispy.HTML(
            format_html('<p class="help-block">{}</p>', help_text)
        )

    @property
    def token_encryption_help_block(self):
        help_text = _(
            'This is a high security feature  that ensures Assertions are '
            'fully encrypted. This feature requires a Premium Azure AD '
            'subscription. '
        )
        return crispy.HTML(
            format_html('<p class="help-block">{}</p>', help_text)
        )

    @property
    def service_provider_fields(self):
        shown_fields = []
        if self.show_help_block:
            shown_fields.append(self.service_provider_help_block)
        shown_fields.extend([
            hqcrispy.B3TextField(
                'sp_entity_id',
                url_helpers.get_saml_entity_id(self.idp),
            ),
            hqcrispy.B3TextField(
                'sp_acs_url',
                url_helpers.get_saml_acs_url(self.idp),
            ),
            hqcrispy.B3TextField(
                'sp_sign_on_url',
                url_helpers.get_saml_login_url(self.idp),
            ),
        ])
        return shown_fields

    @property
    def token_encryption_fields(self):
        download = _("Download")
        return [
            hqcrispy.B3TextField(
                'sp_public_cert',
                format_html(
                    '<a href="?sp_cert_public" target="_blank">{}</a>',
                    download
                ),
            ),
            hqcrispy.B3TextField(
                'sp_public_cert_expiration',
                self.idp.date_sp_cert_expiration.strftime(
                    '%d %B %Y at %H:%M UTC'
                ),
            ),
            hqcrispy.B3TextField(
                'sp_rollover_cert',
                (format_html(
                    '<a href="?sp_rollover_cert_public" target="_blank">{}</a>',
                    download)
                 if self.idp.sp_rollover_cert_public
                 else _("Not needed/generated yet.")),
            ),
        ]


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
        label=ugettext_lazy("Enterprise Console"),
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

        if self.idp.is_editable:
            self.fields['is_editable'].help_text = format_html(
                '<a href="{}">{}</a>',
                url_helpers.get_dashboard_link(self.idp),
                _("Edit Enterprise Settings")
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
                            format_html(
                                '<a href="{}">{}</a>',
                                account_link,
                                identity_provider.owner.name
                            )
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
                        crispy.Div(*sp_details_form.service_provider_fields),
                        crispy.Div(*sp_details_form.token_encryption_fields),
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

    def clean_is_editable(self):
        is_editable = self.cleaned_data['is_editable']
        if is_editable:
            _check_is_editable_requirements(self.idp)
        return is_editable

    def clean_is_active(self):
        is_active = self.cleaned_data['is_active']
        if is_active:
            _check_is_editable_requirements(self.idp)
            required_for_activation = [
                (self.idp.entity_id, _('Entity ID')),
                (self.idp.login_url, _('Login URL')),
                (self.idp.logout_url, _('Logout URL')),
                (self.idp.idp_cert_public
                 and self.idp.date_idp_cert_expiration,
                 _('Public IdP Signing Certificate')),
            ]
            not_filled_out = []
            for requirement, name in required_for_activation:
                if not requirement:
                    not_filled_out.append(name)
            if not_filled_out:
                raise forms.ValidationError(
                    _("Please make sure an enterprise admin has filled out "
                      "the following details before activating SSO globally: "
                      "{}").format(", ".join(not_filled_out))
                )
        return is_active

    @transaction.atomic
    def update_identity_provider(self, admin_user):
        self.idp.name = self.cleaned_data['name']
        self.idp.slug = self.cleaned_data['slug']
        self.idp.is_editable = self.cleaned_data['is_editable']
        self.idp.is_active = self.cleaned_data['is_active']
        self.idp.last_modified_by = admin_user.username
        self.idp.save()
        return self.idp


class SSOEnterpriseSettingsForm(forms.Form):
    """This form manages fields that enterprise admins can update.
    """
    name = forms.CharField(
        label=ugettext_lazy("Name"),
        required=False,
    )
    is_active = forms.BooleanField(
        label=ugettext_lazy("Status"),
        required=False,
        widget=BootstrapCheckboxInput(
            inline_label=ugettext_lazy(
                "Single Sign On is active"
            ),
        ),
        help_text=ugettext_lazy(
            "This will also force users with matching linked email domains "
            "to log in with SSO."
        ),
    )
    linked_email_domains = forms.CharField(
        label=ugettext_lazy("Linked Email Domains"),
        required=False,
    )
    entity_id = forms.CharField(
        label=ugettext_lazy("Azure AD Identifier"),
        required=False,
    )
    login_url = forms.CharField(
        label=ugettext_lazy("Login URL"),
        required=False,
    )
    logout_url = forms.CharField(
        label=ugettext_lazy("Logout URL"),
        required=False,
    )
    idp_cert_public = forms.FileField(
        label=ugettext_lazy("Upload Certificate (Base64)"),
        required=False,
    )
    download_idp_cert_public = forms.CharField(
        label=ugettext_lazy("Certificate (Base64)"),
        required=False,
    )
    date_idp_cert_expiration = forms.CharField(
        label=ugettext_lazy("Certificate Expires On"),
        required=False,
    )
    require_encrypted_assertions = forms.BooleanField(
        label=ugettext_lazy("Token Encryption"),
        required=False,
        widget=BootstrapCheckboxInput(
            inline_label=ugettext_lazy(
                "Use Token Encryption"
            ),
        ),
    )

    def __init__(self, identity_provider, *args, **kwargs):
        self.idp = identity_provider
        kwargs['initial'] = {
            'is_active': identity_provider.is_active,
            'entity_id': identity_provider.entity_id,
            'login_url': identity_provider.login_url,
            'logout_url': identity_provider.logout_url,
            'require_encrypted_assertions': identity_provider.require_encrypted_assertions,
        }
        super().__init__(*args, **kwargs)

        sp_details_form = ServiceProviderDetailsForm(identity_provider)
        self.fields.update(sp_details_form.fields)

        certificate_details = []
        if self.idp.idp_cert_public:
            self.fields['idp_cert_public'].label = _("Upload New Certificate (Base64)")
            certificate_details = [
                hqcrispy.B3TextField(
                    'download_idp_cert_public',
                    format_html(
                        '<a href="?idp_cert_public" target="_blank">{}</a>',
                        _("Download")
                    ),
                ),
                hqcrispy.B3TextField(
                    'date_idp_cert_expiration',
                    self.idp.date_idp_cert_expiration.strftime(
                        '%d %B %Y at %H:%M UTC'
                    ),
                ),
            ]

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Div(
                    crispy.Fieldset(
                        _('Basic SAML Configuration for Azure AD'),
                        *sp_details_form.service_provider_fields
                    ),
                    css_class="panel-body"
                ),
                css_class="panel panel-modern-gray panel-form-only"
            ),
            crispy.Div(
                crispy.Div(
                    crispy.Fieldset(
                        _('Connection Details from Azure AD'),
                        'login_url',
                        'entity_id',
                        'logout_url',
                        crispy.Div(*certificate_details),
                        'idp_cert_public',
                    ),
                    css_class="panel-body"
                ),
                css_class="panel panel-modern-gray panel-form-only"
            ),
            crispy.Div(
                crispy.Div(
                    crispy.Fieldset(
                        _('SAML Token Encryption'),
                        sp_details_form.token_encryption_help_block,
                        twbscrispy.PrependedText('require_encrypted_assertions', ''),
                        crispy.Div(*sp_details_form.token_encryption_fields),
                    ),
                    css_class="panel-body"
                ),
                css_class="panel panel-modern-gray panel-form-only"
            ),
            crispy.Div(
                crispy.Div(
                    crispy.Fieldset(
                        _('Single Sign-On Settings'),
                        hqcrispy.B3TextField(
                            'name',
                            identity_provider.name,
                        ),
                        hqcrispy.B3TextField(
                            'linked_email_domains',
                            ", ".join(identity_provider.get_email_domains()),
                        ),
                        twbscrispy.PrependedText('is_active', ''),
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

    def clean_is_active(self):
        is_active = self.cleaned_data['is_active']
        if is_active:
            _check_is_editable_requirements(self.idp)
        return is_active

    def clean_entity_id(self):
        is_active = bool(self.data.get('is_active'))
        entity_id = self.cleaned_data['entity_id']
        _check_required_when_active(is_active, entity_id)
        return entity_id

    def clean_login_url(self):
        is_active = bool(self.data.get('is_active'))
        login_url = self.cleaned_data['login_url']
        _check_required_when_active(is_active, login_url)
        return login_url

    def clean_logout_url(self):
        is_active = bool(self.data.get('is_active'))
        logout_url = self.cleaned_data['logout_url']
        _check_required_when_active(is_active, logout_url)
        return logout_url

    def clean_idp_cert_public(self):
        is_active = bool(self.data.get('is_active'))
        idp_cert_file = self.cleaned_data['idp_cert_public']
        if idp_cert_file:
            try:
                cert = certificates.get_certificate_from_file(idp_cert_file)
                public_key = certificates.get_public_key(cert)
                date_expiration = certificates.get_expiration_date(cert)
            except certificates.crypto.Error:
                log.exception("Error uploading certificate: bad cert file.")
                raise forms.ValidationError(
                    _("File type not accepted. Please ensure you have "
                      "uploaded a Base64 x509 certificate.")
                )
            if date_expiration <= datetime.datetime.now(tz=date_expiration.tzinfo):
                raise forms.ValidationError(
                    _("This certificate has already expired!")
                )
        else:
            public_key = self.idp.idp_cert_public
            date_expiration = self.idp.date_idp_cert_expiration

        _check_required_when_active(is_active, public_key)
        return public_key, date_expiration

    def update_identity_provider(self, admin_user):
        self.idp.is_active = self.cleaned_data['is_active']
        self.idp.entity_id = self.cleaned_data['entity_id']
        self.idp.login_url = self.cleaned_data['login_url']
        self.idp.logout_url = self.cleaned_data['logout_url']

        public_key, date_expiration = self.cleaned_data['idp_cert_public']
        self.idp.idp_cert_public = public_key
        self.idp.date_idp_cert_expiration = date_expiration

        self.idp.require_encrypted_assertions = self.cleaned_data['require_encrypted_assertions']
        self.idp.last_modified_by = admin_user.username
        self.idp.save()
        return self.idp
