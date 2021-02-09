from django import forms
from django.db import transaction
from django.template.defaultfilters import slugify
from django.utils.translation import ugettext_lazy
from django.utils.translation import ugettext as _

from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy

from corehq.apps.accounting.models import BillingAccount
from corehq.apps.hqwebapp import crispy as hqcrispy
from crispy_forms import bootstrap as twbscrispy
from corehq.apps.sso.models import IdentityProvider


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
            "You will NOT be able to edit this through the Admin UI once the "
            "Identity Provider is created."
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
        slugified_test = slugify(slug)
        if slug != slugified_test:
            raise forms.ValidationError(
                _("You did not enter a valid slug. Did you mean '{}'?").format(slugified_test)
            )
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
