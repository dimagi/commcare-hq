from functools import cached_property

from django.forms.utils import flatatt
from django.utils.html import mark_safe
from django.utils.translation import gettext as _

from django_tables2 import columns

from corehq.apps.hqwebapp.tables.columns import DateTimeStringColumn
from corehq.apps.hqwebapp.tables.elasticsearch.records import (
    UserElasticRecord,
    CaseSearchElasticRecord,
)
from corehq.apps.hqwebapp.tables.elasticsearch.tables import ElasticTable
from corehq.apps.hqwebapp.tables.htmx import BaseHtmxTable
from corehq.apps.integration.kyc.models import KycUser
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import CommCareCase


# TODO Simplify serialization logic and code reuse, a lot of code is repeated
def process_kyc_data_for_table(kyc_user, kyc_config):
    from corehq.motech.const import PASSWORD_PLACEHOLDER
    from corehq.apps.integration.kyc.models import KycVerificationFailureCause

    def get_verification_error_message():
        verification_error = kyc_user.kyc_verification_error
        if verification_error:
            try:
                return KycVerificationFailureCause(verification_error).label
            except ValueError:
                return _('Unknown error')
        return None

    processed_data = {
        'id': kyc_user.user_id,
        'has_invalid_data': False,
        'kyc_verification_status': {
            'status': kyc_user.kyc_verification_status,
            'error_message': get_verification_error_message(),
        },
        'kyc_last_verified_at': kyc_user.kyc_last_verified_at,
    }

    for provider_field, field in kyc_config.get_api_field_to_user_data_map_values().items():
        value = kyc_user.get(field)
        if not value:
            processed_data['has_invalid_data'] = True
        else:
            if kyc_config.is_sensitive_field(provider_field):
                value = PASSWORD_PLACEHOLDER
            processed_data[field] = value

    return processed_data


class KycUserElasticRecord(UserElasticRecord):
    """Clean record class for KYC User-based ES queries (CUSTOM_USER_DATA)"""

    def __init__(self, record, request, kyc_config=None, **kwargs):
        super().__init__(record, request, **kwargs)
        self.kyc_config = kyc_config
        self._processed_data = None

    @cached_property
    def kyc_user(self):
        user_id = self.record.get('_id')
        user_obj = CommCareUser.get_by_user_id(user_id)
        if user_obj:
            return KycUser(self.kyc_config, user_obj)

    def __getitem__(self, item):
        """Process KYC data on access"""
        if self._processed_data is None:
            self._processed_data = process_kyc_data_for_table(self.kyc_user, self.kyc_config)
        if item in self._processed_data:
            return self._processed_data[item]
        return super().__getitem__(item)

    def get(self, item, default=None):
        try:
            return self[item]
        except KeyError:
            return default


class KycCaseElasticRecord(CaseSearchElasticRecord):
    """Clean record class for KYC Case-based ES queries (USER_CASE, OTHER_CASE_TYPE)"""

    def __init__(self, record, request, kyc_config=None, **kwargs):
        super().__init__(record, request, **kwargs)
        self.kyc_config = kyc_config
        self._processed_data = None

    @cached_property
    def kyc_user(self):
        case_id = self.record_id
        case_obj = CommCareCase.objects.get_case(case_id, self.kyc_config.domain)
        if case_obj:
            return KycUser(self.kyc_config, case_obj)

    def __getitem__(self, item):
        """Process KYC data on access"""
        if self._processed_data is None:
            self._processed_data = process_kyc_data_for_table(self.kyc_user, self.kyc_config)

        if item in self._processed_data:
            return self._processed_data[item]

        # Fallback to original ES record data
        return super().__getitem__(item)

    def get(self, item, default=None):
        try:
            return self[item]
        except KeyError:
            return default


class DisableableCheckBoxColumn(columns.CheckBoxColumn):
    invalid_flag_prop_name = 'has_invalid_data'

    def render(self, value, record, bound_column):
        default_attrs = {
            'type': 'checkbox',
            'name': 'selection',
            'value': value,
        }
        # Check if record has the invalid flag
        has_invalid_data = getattr(record, 'has_invalid_data', False) or record.get('has_invalid_data', False)
        if has_invalid_data:
            default_attrs['disabled'] = 'disabled'
        return mark_safe('<input %s/>' % flatatt(default_attrs))


class KycVerifyTable(BaseHtmxTable, ElasticTable):
    # Record class will be set dynamically based on configuration
    record_class = None

    class Meta(BaseHtmxTable.Meta):
        orderable = False

    verify_select = DisableableCheckBoxColumn(
        accessor='id',
        attrs={
            'th__input': {'name': 'select_all'},
        },
    )

    @staticmethod
    def get_extra_columns(kyc_config):
        cols = []
        for field in kyc_config.get_api_field_to_user_data_map_values().values():
            name = field.replace('_', ' ').title()
            cols.append(
                (field, columns.Column(verbose_name=name))
            )
        cols.extend([
            ('kyc_verification_status', columns.TemplateColumn(
                template_name='kyc/partials/kyc_verify_status.html',
                verbose_name=_('KYC Status')
            )),
            ('kyc_last_verified_at', DateTimeStringColumn(
                verbose_name=_('Last Verified')
            )),
            ('verify_btn', columns.TemplateColumn(
                template_name='kyc/partials/kyc_verify_button.html',
                verbose_name=_('Verify')
            )),
        ])
        return cols
