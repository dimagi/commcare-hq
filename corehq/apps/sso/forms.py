import datetime
import logging
import re

from django import forms
from django.db import transaction
from django.template.defaultfilters import slugify
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy, gettext
from django.utils.translation import gettext as _

from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy

from corehq.apps.accounting.models import BillingAccount
from corehq.apps.hqwebapp import crispy as hqcrispy
from crispy_forms import bootstrap as twbscrispy
from corehq.apps.hqwebapp.widgets import BootstrapCheckboxInput
from corehq.apps.sso import certificates
from corehq.apps.sso.models import (
    IdentityProvider,
    IdentityProviderProtocol,
    IdentityProviderType,
    LoginEnforcementType,
)
from corehq.apps.sso.utils import url_helpers
from corehq.apps.sso.utils.url_helpers import get_documentation_url
from corehq.util.strings import get_masked_string

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


def _ensure_entity_id_matches_expected_provider(entity_id, identity_provider):
    if (identity_provider.idp_type == IdentityProviderType.ONE_LOGIN
            and not re.match(r'^https:\/\/[A-za-z\d-]*.onelogin.com\/', entity_id)):
        raise forms.ValidationError(
            _("This is not a valid One Login URL.")
        )


def _get_help_text(identity_provider):
    help_link = get_documentation_url(identity_provider)
    help_text = format_html(
        _('<a href="{}">Please read this guide</a> on how to set up '
          'CommCare HQ with {}.<br />You will need the following '
          'information:'),
        help_link,
        identity_provider.service_name,
    )
    return crispy.HTML(
        format_html('<p class="help-block">{}</p>', help_text)
    )


class CreateIdentityProviderForm(forms.Form):
    """This form initializes the essential fields of an IdentityProvider
    """
    owner = forms.IntegerField(
        label=gettext_lazy("Billing Account Owner"),
        widget=forms.Select(choices=[]),
    )
    protocol = forms.CharField(
        label=gettext_lazy("Protocol"),
        max_length=5,
        widget=forms.Select(choices=IdentityProviderProtocol.CHOICES)
    )
    idp_type = forms.CharField(
        label=gettext_lazy("Service"),
        max_length=50,
        widget=forms.Select(choices=[]),
    )
    name = forms.CharField(
        label=gettext_lazy("Public Name"),
        help_text=gettext_lazy(
            "Users will see this name when logging in."
        ),
        max_length=128,
    )
    slug = forms.CharField(
        label=gettext_lazy("Slug for SP Endpoints"),
        help_text=gettext_lazy(
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
                crispy.Field(
                    'protocol',
                    data_bind="value: protocol",
                ),
                crispy.Field(
                    'idp_type',
                    data_bind="value: idpType, "
                              "options: availableIdpTypes, "
                              "optionsValue: function (item) { return item[0]; }, "
                              "optionsText: function (item) { return item[1]; }",
                ),
                'name',
                'slug',
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    gettext_lazy("Create Identity Provider"),
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

    def clean_idp_type(self):
        idp_type = self.cleaned_data['idp_type']
        protocol = self.cleaned_data['protocol']
        valid_types = [t[0] for t in IdentityProviderProtocol.get_supported_types()[protocol]]
        if idp_type not in valid_types:
            raise forms.ValidationError(
                _("This service does not support the selected protocol."),
            )
        return idp_type

    @transaction.atomic
    def create_identity_provider(self, admin_user):
        owner = BillingAccount.objects.get(id=self.cleaned_data['owner'])
        protocol = self.cleaned_data['protocol']
        idp = IdentityProvider.objects.create(
            owner=owner,
            slug=self.cleaned_data['slug'],
            name=self.cleaned_data['name'],
            created_by=admin_user.username,
            last_modified_by=admin_user.username,
            protocol=protocol,
            idp_type=self.cleaned_data['idp_type'],
        )
        if protocol == IdentityProviderProtocol.SAML:
            idp.create_service_provider_certificate()
        return idp


class RelyingPartyDetailsForm(forms.Form):
    """This form is for display purposes and lists all the OpenID Connect
    information that's required for the Relying Party"""
    login_url = forms.CharField(
        label=gettext_lazy("Login Url"),
        required=False,
    )
    redirect_uris = forms.CharField(
        label=gettext_lazy("Redirect URIs"),
        required=False,
    )
    logout_redirect_uris = forms.CharField(
        label=gettext_lazy("Post Logout Redirect URIs"),
        required=False,
    )

    def __init__(self, identity_provider, *args, **kwargs):
        self.idp = identity_provider
        super().__init__(*args, **kwargs)

        if self.idp.idp_type == IdentityProviderType.OKTA:
            self.fields['redirect_uris'].label = gettext("Sign-in redirect URIs ")
            self.fields['logout_redirect_uris'].label = gettext("Sign-out redirect URIs")
            self.fields['login_url'].label = gettext("Initiate login URI")

    @property
    def application_details_fields(self):
        login_url = url_helpers.get_oidc_login_url(self.idp)
        auth_url = url_helpers.get_oidc_auth_url(self.idp)
        logout_url = url_helpers.get_oidc_logout_url(self.idp)
        if self.idp.idp_type == IdentityProviderType.OKTA:
            return [
                hqcrispy.B3TextField('redirect_uris', auth_url),
                hqcrispy.B3TextField('logout_redirect_uris', logout_url),
                hqcrispy.B3TextField('login_url', login_url),
            ]
        return [
            hqcrispy.B3TextField('login_url', login_url),
            hqcrispy.B3TextField('redirect_uris', auth_url),
            hqcrispy.B3TextField('logout_redirect_uris', logout_url),
        ]


class ServiceProviderDetailsForm(forms.Form):
    """This form is for display purposes and lists all the SAML 2.0
    required service provider information that's needed to link with an
    identity provider."""
    sp_entity_id = forms.CharField(
        label=gettext_lazy("Identifier (Entity ID)"),
        required=False,
    )
    sp_acs_url = forms.CharField(
        label=gettext_lazy("Reply URL (Assertion Consumer Service)"),
        required=False,
    )
    sp_sign_on_url = forms.CharField(
        label=gettext_lazy("Sign on URL"),
        required=False,
    )
    sp_public_cert = forms.CharField(
        label=gettext_lazy("Public x509 Cert"),
        required=False,
    )
    sp_public_cert_expiration = forms.CharField(
        label=gettext_lazy("Certificate Expires On"),
        required=False,
    )
    sp_rollover_cert = forms.CharField(
        label=gettext_lazy("Rollover x509 Cert"),
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
        return _get_help_text(self.idp)

    @property
    def token_encryption_help_block(self):
        if self.idp.idp_type == IdentityProviderType.AZURE_AD:
            help_text = _(
                'This is a high security feature that ensures Assertions are '
                'fully encrypted. This feature requires a Premium Azure AD '
                'subscription.'
            )
        else:
            help_text = _(
                'This feature may or may not be supported by your Identity Provider. '
                'Please refer to their documentation.'
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
        label=gettext_lazy("Billing Account Owner"),
        required=False,
    )
    protocol = forms.CharField(
        label=gettext_lazy("Protocol"),
        required=False,
    )
    idp_type = forms.CharField(
        label=gettext_lazy("Service"),
        required=False,
    )
    slug = forms.CharField(
        label=gettext_lazy("Slug"),
        required=False,
        help_text=gettext_lazy(
            "CAUTION: Changing this value will alter SSO endpoint URLs "
            "below and affect active SSO setups for the client!"
        ),
    )
    name = forms.CharField(
        label=gettext_lazy("Public Name"),
        max_length=128,
        help_text=gettext_lazy(
            "This text is what users will see when logging in with SSO."
        )
    )
    is_editable = forms.BooleanField(
        label=gettext_lazy("Enterprise Console"),
        required=False,
        widget=BootstrapCheckboxInput(
            inline_label=gettext_lazy(
                "Allow Enterprise Admins to edit SSO Enterprise Settings"
            ),
        ),
    )
    is_active = forms.BooleanField(
        label=gettext_lazy("Active Status"),
        required=False,
        widget=BootstrapCheckboxInput(
            inline_label=gettext_lazy(
                "Single Sign On is active"
            ),
        ),
        help_text=gettext_lazy(
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

        current_protocol_name = dict(IdentityProviderProtocol.CHOICES)[self.idp.protocol]

        if self.idp.protocol == IdentityProviderProtocol.SAML:
            sp_details_form = ServiceProviderDetailsForm(
                identity_provider, show_help_block=False
            )
            self.fields.update(sp_details_form.fields)
            sp_or_rp_settings = crispy.Fieldset(
                _('Service Provider Settings'),
                'slug',
                crispy.Div(*sp_details_form.service_provider_fields),
                crispy.Div(*sp_details_form.token_encryption_fields),
            )
        else:
            rp_details_form = RelyingPartyDetailsForm(identity_provider)
            self.fields.update(rp_details_form.fields)
            sp_or_rp_settings = crispy.Fieldset(
                _('Relying Party Settings'),
                'slug',
                crispy.Div(*rp_details_form.application_details_fields),
            )

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
                        hqcrispy.B3TextField(
                            'protocol',
                            current_protocol_name
                        ),
                        hqcrispy.B3TextField(
                            'idp_type',
                            self.idp.service_name
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
                    sp_or_rp_settings,
                    css_class="panel-body"
                ),
                css_class="panel panel-modern-gray panel-form-only"
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    gettext_lazy("Update Configuration"),
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
            if self.idp.protocol == IdentityProviderProtocol.SAML:
                required_for_activation = [
                    (self.idp.entity_id, _('Entity ID')),
                    (self.idp.login_url, _('Login URL')),
                    (self.idp.logout_url, _('Logout URL')),
                    (self.idp.idp_cert_public
                     and self.idp.date_idp_cert_expiration,
                     _('Public IdP Signing Certificate')),
                ]
            else:
                required_for_activation = [
                    (self.idp.entity_id, _('Issuer ID')),
                    (self.idp.client_id, _('Client ID')),
                    (self.idp.client_secret, _('Client Secret')),
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


class BaseSsoEnterpriseSettingsForm(forms.Form):
    """This form manages fields that enterprise admins can update.
    """
    name = forms.CharField(
        label=gettext_lazy("Name"),
        required=False,
    )
    is_active = forms.BooleanField(
        label=gettext_lazy("Status"),
        required=False,
        widget=BootstrapCheckboxInput(
            inline_label=gettext_lazy(
                "Single Sign On is active"
            ),
        ),
        help_text=gettext_lazy(
            "This will also force users with matching linked email domains "
            "to log in with SSO."
        ),
    )
    login_enforcement_type = forms.CharField(
        label=gettext_lazy("Login Enforcement"),
        max_length=10,
        required=False,
        widget=forms.Select(choices=(
            (LoginEnforcementType.GLOBAL, gettext_lazy("Global: All users must use SSO unless exempt")),
            (LoginEnforcementType.TEST, gettext_lazy("Test: Only Test Users are required to use SSO")),
        )),
        help_text=gettext_lazy(
            "When the Identity Provider is active, this determines how users will be "
            "required to login at the homepage."
        )
    )
    linked_email_domains = forms.CharField(
        label=gettext_lazy("Linked Email Domains"),
        required=False,
    )
    entity_id = forms.CharField(
        label=gettext_lazy("Entity ID"),
        required=False,
    )
    enable_user_deactivation = forms.BooleanField(
        required=False,
        label=gettext_lazy("Auto-Deactivation"),
        help_text=gettext_lazy(
            "This option ensures any authorization provided by CommCare "
            "HQ to Web Users using SSO is removed when those users are removed "
            "from Azure AD (Entra ID). This includes automatic deactivation of any "
            "API keys associated with these users."
        ),
        widget=BootstrapCheckboxInput(
            inline_label=gettext_lazy("Automatically deactivate Web Users")
        )
    )
    api_host = forms.CharField(required=False, label=gettext_lazy("Tenant Id"))
    api_id = forms.CharField(required=False, label=gettext_lazy("Application ID"))
    api_secret = forms.CharField(required=False, label=gettext_lazy("Client Secret"))
    date_api_secret_expiration = forms.DateTimeField(
        required=False,
        label=gettext_lazy("Secret Expires On")
    )

    def __init__(self, identity_provider, *args, **kwargs):
        if 'show_remote_user_management' in kwargs:
            self.show_remote_user_management = kwargs.pop('show_remote_user_management')
        else:
            self.show_remote_user_management = False

        self.idp = identity_provider
        initial = kwargs['initial'] = kwargs.get('initial', {}).copy()
        initial.setdefault('enable_user_deactivation', identity_provider.enable_user_deactivation)
        initial.setdefault('api_host', identity_provider.api_host)
        initial.setdefault('api_id', identity_provider.api_id)
        initial.setdefault('date_api_secret_expiration', identity_provider.date_api_secret_expiration)
        super().__init__(*args, **kwargs)

    def get_primary_fields(self):
        return [
            crispy.Div(
                crispy.Div(
                    crispy.Fieldset(
                        _('Single Sign-On Settings'),
                        hqcrispy.B3TextField(
                            'name',
                            self.idp.name,
                        ),
                        hqcrispy.B3TextField(
                            'linked_email_domains',
                            ", ".join(self.idp.get_email_domains()),
                        ),
                        twbscrispy.PrependedText('is_active', ''),
                        'login_enforcement_type',
                    ),
                    css_class="panel-body"
                ),
                css_class="panel panel-modern-gray panel-form-only"
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    gettext_lazy("Update Configuration"),
                    type="submit",
                    css_class="btn btn-primary",
                )
            ),
        ]

    def get_remote_user_management_fields(self):
        masked_api = get_masked_string(self.idp.api_secret)

        api_secret_toggles = crispy.Div(
            crispy.HTML(
                format_html(
                    '<p class="form-control-text" data-bind="hidden: isAPISecretVisible">'
                    '<span id="masked-api-value">{}</span> '
                    '<a href="#" data-bind="click: startEditingAPISecret">{}</a></p>',
                    masked_api,
                    gettext("Update Secret")
                ),
            ),
            crispy.HTML(
                format_html(
                    '<p class="form-control-text" data-bind="visible: isCancelUpdateVisible">'
                    '<a href="#" data-bind="click: cancelEditingAPISecret">{}</a></p>',
                    gettext("Cancel Update")
                ),
            ),
            style="display: none;",  # prevent html showing before knockout is executed, will set visible to false
            data_bind="visible: true",
        )
        return [crispy.Div(
            crispy.Div(
                crispy.Fieldset(
                    _('Remote User Management'),
                    twbscrispy.PrependedText('enable_user_deactivation', ''),
                    'api_host',
                    'api_id',
                    hqcrispy.B3MultiField(
                        gettext("Client Secret"),
                        crispy.Div(
                            hqcrispy.InlineField(
                                'api_secret',
                                data_bind="visible: isAPISecretVisible, "
                                          "textInput: apiSecret"
                            ),
                            api_secret_toggles,
                        ),
                        show_row_class=False,
                    ),
                    crispy.Field('date_api_secret_expiration', css_class='date-picker',
                                 data_bind="textInput: dateApiSecretExpiration"),
                ),
                css_class="panel-body"
            ),
            css_class="panel panel-modern-gray panel-form-only")]

    @staticmethod
    def _check_required_when_enabled(is_enabled, value):
        if is_enabled and not value:
            raise forms.ValidationError(
                _("This is required when Auto-Deactivation is enabled.")
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
        _ensure_entity_id_matches_expected_provider(entity_id, self.idp)
        return entity_id

    def clean_api_secret(self):
        api_secret = self.cleaned_data['api_secret']
        is_enabled = self.cleaned_data['enable_user_deactivation']
        if is_enabled and not (api_secret or self.idp.api_secret):
            raise forms.ValidationError(
                _("This is required when Auto-Deactivation is enabled.")
            )
        return api_secret

    def clean_api_id(self):
        api_id = self.cleaned_data['api_id']
        is_enabled = self.cleaned_data['enable_user_deactivation']
        BaseSsoEnterpriseSettingsForm._check_required_when_enabled(is_enabled, api_id)
        return api_id

    def clean_api_host(self):
        api_host = self.cleaned_data['api_host']
        is_enabled = self.cleaned_data['enable_user_deactivation']
        BaseSsoEnterpriseSettingsForm._check_required_when_enabled(is_enabled, api_host)
        return api_host

    def clean_date_api_secret_expiration(self):
        date_expiration = self.cleaned_data['date_api_secret_expiration']
        is_enabled = self.cleaned_data['enable_user_deactivation']
        BaseSsoEnterpriseSettingsForm._check_required_when_enabled(is_enabled, date_expiration)
        if date_expiration and date_expiration <= datetime.datetime.now(tz=date_expiration.tzinfo):
            raise forms.ValidationError(
                _("This certificate has already expired!")
            )
        return date_expiration

    def update_identity_provider(self, admin_user):
        raise NotImplementedError("please implement update_identity_provider")


class SsoSamlEnterpriseSettingsForm(BaseSsoEnterpriseSettingsForm):
    login_url = forms.CharField(
        label=gettext_lazy("Login URL"),
        required=False,
    )
    logout_url = forms.CharField(
        label=gettext_lazy("Logout URL"),
        required=False,
    )
    idp_cert_public = forms.FileField(
        label=gettext_lazy("Upload Certificate (Base64)"),
        required=False,
    )
    download_idp_cert_public = forms.CharField(
        label=gettext_lazy("Certificate (Base64)"),
        required=False,
    )
    date_idp_cert_expiration = forms.CharField(
        label=gettext_lazy("Certificate Expires On"),
        required=False,
    )
    require_encrypted_assertions = forms.BooleanField(
        label=gettext_lazy("Token Encryption"),
        required=False,
        widget=BootstrapCheckboxInput(
            inline_label=gettext_lazy(
                "Use Token Encryption"
            ),
        ),
    )

    def __init__(self, identity_provider, *args, **kwargs):
        initial = kwargs['initial'] = kwargs.get('initial', {}).copy()
        initial.setdefault('is_active', identity_provider.is_active)
        initial.setdefault('login_enforcement_type', identity_provider.login_enforcement_type)
        initial.setdefault('entity_id', identity_provider.entity_id)
        initial.setdefault('login_url', identity_provider.login_url)
        initial.setdefault('logout_url', identity_provider.logout_url)
        initial.setdefault('require_encrypted_assertions', identity_provider.require_encrypted_assertions)
        super().__init__(identity_provider, *args, **kwargs)

        sp_details_form = ServiceProviderDetailsForm(identity_provider)
        self.fields.update(sp_details_form.fields)

        self.fields['entity_id'].label = _("{} Identifier").format(self.idp.service_name)

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
        layout = crispy.Layout(
            crispy.Div(
                crispy.Div(
                    crispy.Fieldset(
                        _('Basic SAML Configuration for {}').format(self.idp.service_name),
                        *sp_details_form.service_provider_fields
                    ),
                    css_class="panel-body"
                ),
                css_class="panel panel-modern-gray panel-form-only"
            ),
            crispy.Div(
                crispy.Div(
                    crispy.Fieldset(
                        _('Connection Details from {}').format(self.idp.service_name),
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
        )
        if self.show_remote_user_management:
            layout.append(crispy.Div(*self.get_remote_user_management_fields()))
        layout.append(crispy.Div(*self.get_primary_fields()))

        self.helper.layout = layout

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
        self.idp.login_enforcement_type = self.cleaned_data['login_enforcement_type']
        self.idp.entity_id = self.cleaned_data['entity_id']
        self.idp.login_url = self.cleaned_data['login_url']
        self.idp.logout_url = self.cleaned_data['logout_url']

        public_key, date_expiration = self.cleaned_data['idp_cert_public']
        self.idp.idp_cert_public = public_key
        self.idp.date_idp_cert_expiration = date_expiration

        self.idp.require_encrypted_assertions = self.cleaned_data['require_encrypted_assertions']

        self.idp.enable_user_deactivation = self.cleaned_data['enable_user_deactivation']
        self.idp.api_secret = self.cleaned_data['api_secret'] or self.idp.api_secret
        self.idp.api_host = self.cleaned_data['api_host']
        self.idp.api_id = self.cleaned_data['api_id']
        self.idp.date_api_secret_expiration = self.cleaned_data['date_api_secret_expiration']

        self.idp.last_modified_by = admin_user.username
        self.idp.save()
        return self.idp


class SsoOidcEnterpriseSettingsForm(BaseSsoEnterpriseSettingsForm):
    client_id = forms.CharField(
        label=gettext_lazy("Client ID"),
        required=False,
    )
    client_secret = forms.CharField(
        label=gettext_lazy("Client Secret"),
        required=False,
    )

    def __init__(self, identity_provider, *args, **kwargs):
        initial = kwargs['initial'] = kwargs.get('initial', {}).copy()
        initial.setdefault('is_active', identity_provider.is_active)
        initial.setdefault('login_enforcement_type', identity_provider.login_enforcement_type)
        initial.setdefault('entity_id', identity_provider.entity_id)
        initial.setdefault('client_id', identity_provider.client_id)
        initial.setdefault('client_secret', identity_provider.client_secret)
        super().__init__(identity_provider, *args, **kwargs)

        rp_details_form = RelyingPartyDetailsForm(identity_provider)
        self.fields.update(rp_details_form.fields)

        if self.idp.idp_type == IdentityProviderType.ONE_LOGIN:
            self.fields['entity_id'].label = _("Issuer URL")
        elif self.idp.idp_type == IdentityProviderType.OKTA:
            self.fields['entity_id'].label = _("Issuer URI")

        if self.idp.client_secret:
            client_secret_toggles = crispy.Div(
                crispy.HTML(
                    format_html(
                        '<p class="form-control-text"><a href="#" data-bind="click: showClientSecret, '
                        'visible: isClientSecretHidden">{}</a></p>',
                        gettext("Show Secret")
                    ),
                ),
                crispy.HTML(
                    format_html(
                        '<p class="form-control-text" data-bind="visible: isClientSecretVisible">'
                        '<a href="#" data-bind="click: hideClientSecret">{}</a></p>',
                        gettext("Hide Secret")
                    ),
                ),
            )
        else:
            client_secret_toggles = crispy.Div()

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Div(
                    crispy.Fieldset(
                        _('Application Details for {}').format(self.idp.service_name),
                        _get_help_text(self.idp),
                        crispy.Div(*rp_details_form.application_details_fields),
                    ),
                    css_class="panel-body"
                ),
                css_class="panel panel-modern-gray panel-form-only"
            ),
            crispy.Div(
                crispy.Div(
                    crispy.Fieldset(
                        _('OpenID Provider Configuration'),
                        'client_id',
                        hqcrispy.B3MultiField(
                            gettext("Client Secret"),
                            crispy.Div(
                                hqcrispy.InlineField(
                                    'client_secret',
                                    data_bind="visible: isClientSecretVisible"
                                ),
                                client_secret_toggles,
                            ),
                            show_row_class=False,
                        ),
                        'entity_id',
                    ),
                    css_class="panel-body"
                ),
                css_class="panel panel-modern-gray panel-form-only"
            ),
            crispy.Div(*self.get_primary_fields()),
        )

    def clean_client_id(self):
        is_active = bool(self.data.get('is_active'))
        client_id = self.cleaned_data['client_id']
        _check_required_when_active(is_active, client_id)
        return client_id

    def clean_client_secret(self):
        is_active = bool(self.data.get('is_active'))
        client_secret = self.cleaned_data['client_secret']
        _check_required_when_active(is_active, client_secret)
        return client_secret

    def update_identity_provider(self, admin_user):
        self.idp.is_active = self.cleaned_data['is_active']
        self.idp.login_enforcement_type = self.cleaned_data['login_enforcement_type']
        self.idp.entity_id = self.cleaned_data['entity_id']
        self.idp.client_id = self.cleaned_data['client_id']
        self.idp.client_secret = self.cleaned_data['client_secret']

        self.idp.last_modified_by = admin_user.username
        self.idp.save()
        return self.idp
