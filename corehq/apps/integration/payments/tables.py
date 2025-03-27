from django.forms.utils import flatatt
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from django_tables2 import columns

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
        return PaymentStatus(value).label
