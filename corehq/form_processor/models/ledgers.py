from collections import namedtuple

from django.db import models

from memoized import memoized

from corehq.sql_db.models import PartitionedModel
from corehq.util.models import TruncatingCharField

from ..track_related import TrackRelatedChanges
from .mixin import SaveStateMixin


class LedgerValue(PartitionedModel, SaveStateMixin, models.Model, TrackRelatedChanges):
    """
    Represents the current state of a ledger.
    """
    partition_attr = 'case_id'

    domain = models.CharField(max_length=255, null=False, default=None)
    case = models.ForeignKey(
        'CommCareCase', to_field='case_id', db_index=False, on_delete=models.CASCADE
    )
    # can't be a foreign key to products because of sharding.
    # also still unclear whether we plan to support ledgers to non-products
    entry_id = models.CharField(max_length=100, default=None)
    section_id = models.CharField(max_length=100, default=None)
    balance = models.IntegerField(default=0)
    last_modified = models.DateTimeField(db_index=True)
    last_modified_form_id = models.CharField(max_length=100, null=True, default=None)
    daily_consumption = models.DecimalField(max_digits=20, decimal_places=5, null=True)

    def natural_key(self):
        # necessary for dumping models from a sharded DB so that we exclude the
        # SQL 'id' field which won't be unique across all the DB's
        return self.case_id, self.section_id, self.entry_id

    @property
    def last_modified_date(self):
        return self.last_modified

    @property
    def product_id(self):
        return self.entry_id

    @property
    def stock_on_hand(self):
        return self.balance

    @property
    def ledger_reference(self):
        from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference
        return UniqueLedgerReference(
            case_id=self.case_id, section_id=self.section_id, entry_id=self.entry_id
        )

    @property
    def ledger_id(self):
        return self.ledger_reference.as_id()

    @property
    @memoized
    def location(self):
        from corehq.apps.locations.models import SQLLocation
        return SQLLocation.objects.get_or_None(supply_point_id=self.case_id)

    @property
    def sql_location(self):
        return self.location

    @property
    @memoized
    def sql_product(self):
        from corehq.apps.products.models import SQLProduct
        try:
            return SQLProduct.objects.get(domain=self.domain, product_id=self.entry_id)
        except SQLProduct.DoesNotExist:
            return None

    @property
    def location_id(self):
        return self.location.location_id if self.location else None

    def to_json(self, include_location_id=True):
        from ..serializers import LedgerValueSerializer
        serializer = LedgerValueSerializer(self, include_location_id=include_location_id)
        return dict(serializer.data)

    def __repr__(self):
        return "LedgerValue(" \
               "case_id={s.case_id}, " \
               "section_id={s.section_id}, " \
               "entry_id={s.entry_id}, " \
               "balance={s.balance}".format(s=self)

    class Meta(object):
        app_label = "form_processor"
        db_table = "form_processor_ledgervalue"
        unique_together = ("case", "section_id", "entry_id")


class LedgerTransaction(PartitionedModel, SaveStateMixin, models.Model):
    partition_attr = 'case_id'

    TYPE_BALANCE = 1
    TYPE_TRANSFER = 2
    TYPE_CHOICES = (
        (TYPE_BALANCE, 'balance'),
        (TYPE_TRANSFER, 'transfer'),
    )

    form_id = models.CharField(max_length=255, null=False)
    server_date = models.DateTimeField()
    report_date = models.DateTimeField()
    type = models.PositiveSmallIntegerField(choices=TYPE_CHOICES)
    case = models.ForeignKey(
        'CommCareCase', to_field='case_id', db_index=False, on_delete=models.CASCADE
    )
    entry_id = models.CharField(max_length=100, default=None)
    section_id = models.CharField(max_length=100, default=None)

    user_defined_type = TruncatingCharField(max_length=20, null=True, blank=True)

    # change from previous balance
    delta = models.BigIntegerField(default=0)
    # new balance
    updated_balance = models.BigIntegerField(default=0)

    def natural_key(self):
        # necessary for dumping models from a sharded DB so that we exclude the
        # SQL 'id' field which won't be unique across all the DB's
        return self.case_id, self.form_id, self.section_id, self.entry_id

    def get_consumption_transactions(self, exclude_inferred_receipts=False):
        """
        This adds in the inferred transactions for BALANCE transactions and converts
        TRANSFER transactions to ``consumption`` / ``receipts``
        :return: list of ``ConsumptionTransaction`` objects
        """
        from casexml.apps.stock.const import (
            TRANSACTION_TYPE_STOCKONHAND,
            TRANSACTION_TYPE_RECEIPTS,
            TRANSACTION_TYPE_CONSUMPTION
        )
        transactions = [
            ConsumptionTransaction(
                TRANSACTION_TYPE_RECEIPTS if self.delta > 0 else TRANSACTION_TYPE_CONSUMPTION,
                abs(self.delta),
                self.report_date
            )
        ]
        if self.type == LedgerTransaction.TYPE_BALANCE:
            if self.delta > 0 and exclude_inferred_receipts:
                transactions = []

            transactions.append(
                ConsumptionTransaction(
                    TRANSACTION_TYPE_STOCKONHAND,
                    self.updated_balance,
                    self.report_date
                )
            )
        return transactions

    @property
    def readable_type(self):
        for type_, type_slug in self.TYPE_CHOICES:
            if self.type == type_:
                return type_slug

    @property
    def ledger_reference(self):
        from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference
        return UniqueLedgerReference(
            case_id=self.case_id, section_id=self.section_id, entry_id=self.entry_id
        )

    @property
    def stock_on_hand(self):
        return self.updated_balance

    def __str__(self):
        return (
            "LedgerTransaction("
            "form_id='{self.form_id}', "
            "server_date='{self.server_date}', "
            "report_date='{self.report_date}', "
            "type='{self.readable_type}', "
            "case_id='{self.case_id}', "
            "entry_id='{self.entry_id}', "
            "section_id='{self.section_id}', "
            "user_defined_type='{self.user_defined_type}', "
            "delta='{self.delta}', "
            "updated_balance='{self.updated_balance}')"
        ).format(self=self)

    class Meta(object):
        db_table = "form_processor_ledgertransaction"
        app_label = "form_processor"
        # note: can't put a unique constraint here (case_id, form_id, section_id, entry_id)
        # since a single form can make multiple updates to a ledger
        index_together = [
            ["case", "section_id", "entry_id"],
        ]
        indexes = [models.Index(fields=['form_id'])]


class ConsumptionTransaction(namedtuple('ConsumptionTransaction', ['type', 'normalized_value', 'received_on'])):

    @property
    def is_stockout(self):
        from casexml.apps.stock.const import TRANSACTION_TYPE_STOCKONHAND
        return self.type == TRANSACTION_TYPE_STOCKONHAND and self.normalized_value == 0

    @property
    def is_checkpoint(self):
        from casexml.apps.stock.const import TRANSACTION_TYPE_STOCKONHAND
        return self.type == TRANSACTION_TYPE_STOCKONHAND and not self.is_stockout
