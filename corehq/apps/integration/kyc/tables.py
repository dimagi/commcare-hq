from functools import cached_property
from django.forms.utils import flatatt
from django.utils.html import mark_safe
from django.utils.translation import gettext as _

from django_tables2 import columns

from corehq.apps.hqwebapp.tables.columns import DateTimeStringColumn
from corehq.apps.hqwebapp.tables.elasticsearch.records import CaseSearchElasticRecord, UserElasticRecord
from corehq.apps.hqwebapp.tables.elasticsearch.tables import ElasticTable
from corehq.apps.hqwebapp.tables.htmx import BaseHtmxTable
from corehq.apps.integration.kyc.models import KycUser
from corehq.motech.const import PASSWORD_PLACEHOLDER


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


def serialize_kyc_data_for_table(kyc_user, kyc_config):
    """
    Serialize KYC data for table display based on fields defined in API config.
    Masks sensitive fields and flags invalid data.
    """
    serialized_data = {
        "id": kyc_user.user_id,
        "has_invalid_data": False,
        "kyc_verification_status": {
            "status": kyc_user.kyc_verification_status,
            "error_message": kyc_user.verification_error_message,
        },
        "kyc_last_verified_at": kyc_user.kyc_last_verified_at,
    }

    for provider_field, field in kyc_config.get_api_field_to_user_data_map_values().items():
        value = kyc_user.get(field)
        if not value:
            serialized_data["has_invalid_data"] = True
        else:
            if kyc_config.is_sensitive_field(provider_field):
                value = PASSWORD_PLACEHOLDER
            serialized_data[field] = value

    return serialized_data


class KycElasticRecordMixin:

    @property
    def kyc_user(self):
        raise NotImplementedError("Subclasses must implement 'kyc_user' property.")

    @cached_property
    def serialized_data(self):
        try:
            if self.kyc_user:
                return serialize_kyc_data_for_table(self.kyc_user, self.kyc_config)
            return None
        except Exception:
            return None

    def __getitem__(self, item):
        if self.serialized_data and item in self.serialized_data:
            return self.serialized_data[item]
        return None

    def get(self, item, default=None):
        return self.__getitem__(item) or default


class KycUserElasticRecord(KycElasticRecordMixin, UserElasticRecord):
    """Record class for KYC User-based ES queries (CUSTOM_USER_DATA)."""

    def __init__(self, record, request, kyc_config=None, **kwargs):
        super().__init__(record, request, **kwargs)
        self.kyc_config = kyc_config

    @property
    def kyc_user(self):
        return KycUser(self.kyc_config, self.record) if self.record else None


class KycCaseElasticRecord(KycElasticRecordMixin, CaseSearchElasticRecord):
    """Record class for KYC Case-based ES queries (USER_CASE, OTHER_CASE_TYPE)."""

    def __init__(self, record, request, kyc_config=None, **kwargs):
        super().__init__(record, request, **kwargs)
        self.kyc_config = kyc_config

    @cached_property
    def kyc_user(self):
        return KycUser(self.kyc_config, self.record.case) if self.record.case else None


class KycVerifyTable(BaseHtmxTable, ElasticTable):
    # Record class is set dynamically based on user data configuration
    record_class = None

    class Meta(BaseHtmxTable.Meta):
        pass

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
