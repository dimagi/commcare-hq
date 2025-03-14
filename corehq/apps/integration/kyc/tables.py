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

    @staticmethod
    def get_extra_columns(kyc_config):
        cols = [
            ('verify_select', DisableableCheckBoxColumn(
                accessor='id',
                attrs={
                    'th__input': {'name': 'select_all'},
                },
            ))
        ]
        for field in kyc_config.api_field_to_user_data_map.values():
            # TODO: We could look up a verbose name using the data
            #       dictionary or custom user field label
            name = field.replace('_', ' ').title()
            cols.append((field, columns.Column(verbose_name=name)))
        cols.extend([
            ('kyc_verification_status', columns.TemplateColumn(
                template_name='kyc/partials/kyc_verify_status.html',
                verbose_name=_('KYC Status'),
            )),
            ('kyc_last_verified_at', columns.DateTimeColumn(
                verbose_name=_('Last Verified'),
            )),
            ('verify_btn', columns.TemplateColumn(
                template_name='kyc/partials/kyc_verify_button.html',
                verbose_name=_('Verify'),
            )),
        ])
        return cols
