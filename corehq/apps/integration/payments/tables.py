from django.forms.utils import flatatt
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from django_tables2 import columns

from corehq.apps.hqwebapp.tables.columns import DateTimeStringColumn
from corehq.apps.hqwebapp.tables.elasticsearch.records import CaseSearchElasticRecord
from corehq.apps.hqwebapp.tables.elasticsearch.tables import ElasticTable
from corehq.apps.hqwebapp.tables.htmx import BaseHtmxTable
from corehq.apps.integration.payments.const import PaymentStatus


class PaymentsVerifyTable(BaseHtmxTable, ElasticTable):
    OPTIONAL_FIELDS = [
        'verify_select',
        'payment_verified',
        'payment_verified_by',
        'payment_status',
        'payment_timestamp',
        'kyc_status',
    ]

    record_class = CaseSearchElasticRecord

    class Meta(BaseHtmxTable.Meta):
        pass

    verify_select = columns.CheckBoxColumn(
        accessor='case_id',
        attrs={
            'th__input': {'name': 'select_all'},
        },
        verbose_name=_("Verify Selected"),
    )
    batch_number = columns.Column(
        verbose_name=_("Batch Number"),
    )
    phone_number = columns.Column(
        verbose_name=_("Phone Number"),
    )
    email = columns.Column(
        verbose_name=_("Email Address"),
    )
    amount = columns.Column(
        verbose_name=_("Amount"),
    )
    currency = columns.Column(
        verbose_name=_("Currency"),
    )
    user_or_case_id = columns.Column(
        verbose_name=_("User or Case ID"),
    )
    kyc_status = columns.Column(
        verbose_name=_("KYC Status"),
        # Since by default the value for kyc_status is blank,
        # in which case render_kyc_status will be skipped.
        # We set empty_values explicitly to force render_kyc_status being called for all rows.
        empty_values=(),
    )
    payee_note = columns.Column(
        verbose_name=_("Payee Note"),
    )
    payer_message = columns.Column(
        verbose_name=_("Payer Message"),
    )
    payment_verified = columns.Column(
        verbose_name=_("Verified"),
    )
    payment_verified_by = columns.Column(
        verbose_name=_("Verified By"),
    )
    payment_status = columns.Column(
        verbose_name=_("Payment Status"),
        empty_values=(),
    )
    payment_timestamp = DateTimeStringColumn(
        verbose_name=_("Submitted At"),
    )

    def render_verify_select(self, record, value):
        default_attrs = {
            'type': 'checkbox',
            'name': 'selection',
            'value': value,
        }
        required_fields = list(set(self.base_columns.keys()) - set(self.OPTIONAL_FIELDS))

        for field in required_fields:
            if not record.record.get(field):
                default_attrs['disabled'] = 'disabled'
                break
        return mark_safe('<input %s/>' % flatatt(default_attrs))

    def render_payment_status(self, record, value):
        try:
            return PaymentStatus.from_value(value).label
        except ValueError:
            return _("Invalid Status")

    def render_kyc_status(self, record, value):
        user_or_case_id = record.record.get('user_or_case_id')
        if user_or_case_id and user_or_case_id in self.context['verification_statuses']:
            return self.context['verification_statuses'][user_or_case_id]
        return _("Unavailable")
