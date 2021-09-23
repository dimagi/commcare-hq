from decimal import Decimal
from django.db.models.signals import pre_save
from django.dispatch import receiver
from casexml.apps.stock import const
from casexml.apps.stock.models import StockTransaction


@receiver(pre_save, sender=StockTransaction)
def stock_transaction_pre_save_signal_receiver(sender, instance, *args, **kwargs):
    create_reconciliation_transaction(instance)
    populate_sql_product(instance)


def create_reconciliation_transaction(instance):
    from corehq.apps.commtrack.consumption import should_exclude_invalid_periods

    creating = instance.pk is None
    if creating and instance.type == const.TRANSACTION_TYPE_STOCKONHAND:
        previous_transaction = instance.get_previous_transaction()
        # only soh reports that have changed the stock create inferred transactions
        if previous_transaction and previous_transaction.stock_on_hand != instance.stock_on_hand:
            amt = instance.stock_on_hand - Decimal(previous_transaction.stock_on_hand)
            if not should_exclude_invalid_periods(instance.report.domain) or amt < 0:
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


def populate_sql_product(instance):
    from corehq.apps.products.models import SQLProduct

    # some day StockTransaction.sql_product should be the canonical source of
    # the couch product_id, but until then lets not force people to
    # look up the SQLProduct every time..
    if not instance.sql_product_id and instance.product_id:
        instance.sql_product = SQLProduct.objects.get(product_id=instance.product_id)
