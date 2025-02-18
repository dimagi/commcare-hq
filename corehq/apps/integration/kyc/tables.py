from django.forms.utils import flatatt
from django.utils.html import mark_safe
from django.utils.translation import gettext as _

from django_tables2 import columns

from corehq.apps.hqwebapp.tables.htmx import BaseHtmxTable


class DisableableCheckBoxColumn(columns.CheckBoxColumn):
    invalid_flag_prop_name = 'has_invalid_data'

    def render(self, value, record, bound_column):
        default_attrs = {
            'type': 'checkbox',
            'name': 'selection',
            'value': value,
        }
        if record.get(self.invalid_flag_prop_name, False):
            default_attrs['disabled'] = 'disabled'
        return mark_safe('<input %s/>' % flatatt(default_attrs))


class KycVerifyTable(BaseHtmxTable):
    class Meta(BaseHtmxTable.Meta):
        pass

    verify_select = DisableableCheckBoxColumn(
        accessor='id',
        attrs={
            'th__input': {'name': 'select_all'},
        },
    )
    first_name = columns.Column(
        verbose_name=_('First Name'),
    )
    last_name = columns.Column(
        verbose_name=_('Last Name'),
    )
    phone_number = columns.Column(
        verbose_name=_('Phone Number'),
    )
    email = columns.Column(
        verbose_name=_('Email Address'),
    )
    national_id_number = columns.Column(
        verbose_name=_('National ID Number'),
    )
    street_address = columns.Column(
        verbose_name=_('Street Address'),
    )
    city = columns.Column(
        verbose_name=_('City'),
    )
    post_code = columns.Column(
        verbose_name=_('Post Code'),
    )
    country = columns.Column(
        verbose_name=_('Country'),
    )
    verify_btn = columns.TemplateColumn(
        template_name='kyc/partials/kyc_verify_button.html',
        verbose_name=_('Verify'),
    )
