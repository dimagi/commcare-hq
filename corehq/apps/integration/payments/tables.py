from django.forms.utils import flatatt
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from django_tables2 import columns

from corehq.apps.hqwebapp.tables.elasticsearch.records import CaseSearchElasticRecord
from corehq.apps.hqwebapp.tables.elasticsearch.tables import ElasticTable
from corehq.apps.hqwebapp.tables.htmx import BaseHtmxTable


class PaymentsVerifyTable(BaseHtmxTable, ElasticTable):
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

    def render_verify_select(self, record, value):
        default_attrs = {
            'type': 'checkbox',
            'name': 'selection',
            'value': value,
        }
        # All columns are required except the checkbox
        required_fields = list(self.base_columns.keys())
        required_fields.remove('verify_select')

        for field in required_fields:
            if not record.record.get(field):
                default_attrs['disabled'] = 'disabled'
                break
        return mark_safe('<input %s/>' % flatatt(default_attrs))
