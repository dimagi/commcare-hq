import re
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from casexml.apps.stock import const
from decimal import Decimal
from corehq.apps.products.models import SQLProduct
from south.modelsinspector import add_introspection_rules


class TruncatingFieldMixin(object):
    """
    http://stackoverflow.com/a/3460942
    """
    def get_prep_value(self, value):
        value = super(TruncatingFieldMixin, self).get_prep_value(value)
        if value:
            return value[:self.max_length]
        return value


class TruncatingCharField(TruncatingFieldMixin, models.CharField):
    pass


class TruncatingTextField(TruncatingFieldMixin, models.TextField):
    pass


# http://south.aeracode.org/wiki/MyFieldsDontWork
paths = [
    TruncatingCharField.__module__ + '.' + TruncatingCharField.__name__,
    TruncatingTextField.__module__ + '.' + TruncatingTextField.__name__,
]
add_introspection_rules([], ["^{}".format(re.escape(path)) for path in paths])


class StockReport(models.Model):
    form_id = models.CharField(max_length=100, db_index=True)
    date = models.DateTimeField(db_index=True)
    type = models.CharField(max_length=20)  # currently "balance" or "transfer"
    domain = models.CharField(max_length=255, null=True)

    # todo: there are properties like these that could be really useful for queries
    # and reports - should decide which ones we want to add if any.
    # they are all redundant via form_id linkage

    # server_date = models.DateTimeField(default=datetime.utcnow, db_index=True)
    # user_id = models.CharField(max_length=100, db_index=True)

    def __unicode__(self):
        return '{type} on {date} ({form})'.format(type=self.type, date=self.date, form=self.form_id)


class StockTransaction(models.Model):
    report = models.ForeignKey(StockReport)
    sql_product = models.ForeignKey(SQLProduct)

    section_id = models.CharField(max_length=100, db_index=True)

    # for now, a supply point or requisition case
    case_id = models.CharField(max_length=100, db_index=True)
    product_id = models.CharField(max_length=100, db_index=True)

    # currently supported/expected: 'stockonhand', 'receipts', 'consumption'
    type = models.CharField(max_length=20)
    # e.g. 'loss', 'transfer', 'inferred'
    subtype = TruncatingTextField(max_length=40, null=True, blank=True)

    # often one of these two will be derived based on the other one
    quantity = models.DecimalField(null=True, max_digits=20, decimal_places=5)
    stock_on_hand = models.DecimalField(max_digits=20, decimal_places=5)

    def __unicode__(self):
        return '{type} of {quantity} to {soh} (case: {case}, product: {product}, section id: {section_id})'.format(
            type=self.type, quantity=self.quantity, soh=self.stock_on_hand,
            case=self.case_id, product=self.product_id, section_id=self.section_id,
        )

    def get_previous_transaction(self):
        siblings = StockTransaction._peer_qs(self.case_id, self.section_id, self.product_id).exclude(pk=self.pk)
        if siblings.count():
            return siblings[0]

    @classmethod
    def latest(cls, case_id, section_id, product_id):
        relevant = cls._peer_qs(case_id, section_id, product_id)
        try:
            return relevant.select_related()[0]
        except IndexError:
            return None

    @classmethod
    def _peer_qs(self, case_id, section_id, product_id):
        return StockTransaction.objects.filter(
            case_id=case_id, product_id=product_id, section_id=section_id).order_by('-report__date', '-pk')


class DocDomainMapping(models.Model):
    """
    Used to store the relationship between a doc and the
    domain it belongs to for efficient lookup
    """
    doc_id = models.CharField(max_length=100, db_index=True, primary_key=True)
    doc_type = models.CharField(max_length=100, db_index=True)
    domain_name = models.CharField(max_length=100, db_index=True)


# signal catchers
@receiver(pre_save, sender=StockTransaction)
def create_reconciliation_transaction(sender, instance, *args, **kwargs):
    creating = instance.pk is None
    if creating and instance.type == const.TRANSACTION_TYPE_STOCKONHAND:
        previous_transaction = instance.get_previous_transaction()
        # only soh reports that have changed the stock create inferred transactions
        if previous_transaction and previous_transaction.stock_on_hand != instance.stock_on_hand:
            amt = instance.stock_on_hand - Decimal(previous_transaction.stock_on_hand)
            domain = instance.report.domain
            exclude_invalid_periods = False
            if domain:
                from corehq.apps.commtrack.models import CommtrackConfig
                config = CommtrackConfig.for_domain(domain)
                if config:
                    exclude_invalid_periods = config.consumption_config.exclude_invalid_periods
            if not domain or not exclude_invalid_periods or amt < 0:
                StockTransaction.objects.create(
                    report=instance.report,
                    case_id=instance.case_id,
                    section_id=instance.section_id,
                    product_id=instance.product_id,
                    type=const.TRANSACTION_TYPE_CONSUMPTION if amt < 0 else const.TRANSACTION_TYPE_RECEIPTS,
                    quantity=amt,
                    stock_on_hand=instance.stock_on_hand,
                    subtype=const.TRANSACTION_SUBTYPE_INFERRED,
                )


@receiver(pre_save, sender=StockTransaction)
def populate_sql_product(sender, instance, *args, **kwargs):
    # some day StockTransaction.sql_product should be the canonical source of
    # the couch product_id, but until then lets not force people to
    # look up the SQLProduct every time..
    if not instance.sql_product_id and instance.product_id:
        instance.sql_product = SQLProduct.objects.get(product_id=instance.product_id)
