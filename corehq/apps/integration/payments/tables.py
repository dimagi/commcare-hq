from django.utils.translation import gettext as _

from django_tables2 import columns

from corehq.apps.hqwebapp.tables.elasticsearch.records import CaseSearchElasticRecord
from corehq.apps.hqwebapp.tables.elasticsearch.tables import ElasticTable
from corehq.apps.hqwebapp.tables.htmx import BaseHtmxTable, DisableableCheckBoxColumn


class PaymentsVerifyTable(BaseHtmxTable, ElasticTable):
    record_class = CaseSearchElasticRecord

    class Meta(BaseHtmxTable.Meta):
        pass

    batch_number = columns.Column(
        verbose_name=_("Batch Number"),
    )
    case_id = columns.Column(
        verbose_name=_("User or Case Id"),
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
    payee_note = columns.Column(
        verbose_name=_("Payee Note"),
    )
    payer_message = columns.Column(
        verbose_name=_("Payer Message"),
    )
    verify_select = DisableableCheckBoxColumn(
        accessor='id',
        attrs={
            'th__input': {'name': 'select_all'},
        },
        verbose_name=_("Verify"),
    )
