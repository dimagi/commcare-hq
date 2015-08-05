import re

from django.db import models
from south.modelsinspector import add_introspection_rules

from corehq.apps.products.models import SQLProduct


class TruncatingCharField(models.CharField):
    """
    http://stackoverflow.com/a/3460942
    """
    def get_prep_value(self, value):
        value = super(TruncatingCharField, self).get_prep_value(value)
        if value:
            return value[:self.max_length]
        return value


# http://south.aeracode.org/wiki/MyFieldsDontWork
path = TruncatingCharField.__module__ + '.' + TruncatingCharField.__name__
add_introspection_rules([], ["^{}".format(re.escape(path))])


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
    subtype = TruncatingCharField(max_length=20, null=True, blank=True)

    # often one of these two will be derived based on the other one
    quantity = models.DecimalField(null=True, max_digits=20, decimal_places=5)
    stock_on_hand = models.DecimalField(max_digits=20, decimal_places=5)

    def __unicode__(self):
        return '{type} of {quantity} to {soh} (case: {case}, product: {product}, section id: {section_id})'.format(
            type=self.type, quantity=self.quantity, soh=self.stock_on_hand,
            case=self.case_id, product=self.product_id, section_id=self.section_id,
        )

    def get_previous_transaction(self):
        siblings = StockTransaction.get_ordered_transactions_for_stock(
            self.case_id, self.section_id, self.product_id).exclude(pk=self.pk)
        if siblings.count():
            return siblings[0]

    @classmethod
    def latest(cls, case_id, section_id, product_id):
        relevant = cls.get_ordered_transactions_for_stock(
            case_id, section_id, product_id)
        try:
            return relevant.select_related()[0]
        except IndexError:
            return None

    @classmethod
    def get_ordered_transactions_for_stock(cls, case_id, section_id, product_id):
        return StockTransaction.objects.filter(
            case_id=case_id, product_id=product_id, section_id=section_id
        ).order_by('-report__date', '-pk')

    class Meta:
        index_together = [
            ['case_id', 'product_id', 'section_id']
        ]


class DocDomainMapping(models.Model):
    """
    Used to store the relationship between a doc and the
    domain it belongs to for efficient lookup
    """
    doc_id = models.CharField(max_length=100, db_index=True, primary_key=True)
    doc_type = models.CharField(max_length=100, db_index=True)
    domain_name = models.CharField(max_length=100, db_index=True)

from .signals import *
