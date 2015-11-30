from django.db import models
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


class StockReport(models.Model):
    form_id = models.CharField(max_length=100, db_index=True)
    date = models.DateTimeField(db_index=True)
    type = models.CharField(max_length=20)  # currently "balance" or "transfer"
    domain = models.CharField(max_length=255, null=True)
    # should always equal
    # FormData.objects.get(instance_id=self.form_id).received_on
    server_date = models.DateTimeField(null=True)

    # todo: there are properties like these that could be really useful for queries
    # and reports - should decide which ones we want to add if any.
    # they are all redundant via form_id linkage

    # server_date = models.DateTimeField(default=datetime.utcnow, db_index=True)
    # user_id = models.CharField(max_length=100, db_index=True)

    def __unicode__(self):
        return '{type} on {date} ({form})'.format(type=self.type, date=self.date, form=self.form_id)

    class Meta:
        app_label = 'stock'


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

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        # this is a bit hacky, but allows us to create StockReport and StockTransaction objects
        # in a place that isn't exactly where we save them, which fits better with the current
        # form processing workflows
        if self.report_id is None and self.report and self.report.id is not None:
            self.report_id = self.report.id
        super(StockTransaction, self).save(
            force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields
        )

    def get_previous_transaction(self):
        siblings = StockTransaction.get_ordered_transactions_for_stock(
            self.case_id, self.section_id, self.product_id).exclude(pk=self.pk)
        if siblings.count():
            return siblings[0]

    @classmethod
    def latest(cls, case_id, section_id, product_id):
        relevant = cls.get_ordered_transactions_for_stock(case_id, section_id, product_id)
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
        app_label = 'stock'
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

    class Meta:
        app_label = 'stock'


from .signals import *
