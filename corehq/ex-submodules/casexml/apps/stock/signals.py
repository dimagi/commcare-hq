from __future__ import absolute_import
from __future__ import unicode_literals
from decimal import Decimal
import logging
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from casexml.apps.stock import const
from casexml.apps.stock.consumption import compute_daily_consumption
from casexml.apps.stock.models import StockTransaction
from corehq.apps.domain.models import Domain


@receiver(pre_save, sender=StockTransaction)
def stock_transaction_pre_save_signal_receiver(sender, instance, *args, **kwargs):
    create_reconciliation_transaction(instance)
    populate_sql_product(instance)


@receiver(post_save, sender=StockTransaction)
def stock_transaction_post_save_signal_receiver(sender, instance, *args, **kwargs):
    update_stock_state_for_transaction(instance)


@receiver(post_delete, sender=StockTransaction)
def stock_transaction_post_delete_signal_receiver(sender, instance, *args,
                                                  **kwargs):
    stock_state_deleted(instance)


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


def update_stock_state_for_transaction(transaction):
    state = get_stock_state_for_transaction(transaction)
    state.save()


def get_stock_state_for_transaction(transaction):
    from corehq.apps.commtrack.models import StockState
    from corehq.apps.locations.models import SQLLocation
    from corehq.apps.products.models import SQLProduct

    # todo: in the worst case, this function makes
    # - three calls to couch (for the case, domain, and commtrack config)
    # - four postgres queries (transacitons, product, location, and state)
    # - one postgres write (to save the state)
    # and that doesn't even include the consumption calc, which can do a whole
    # bunch more work and hit the database.
    sql_product = SQLProduct.objects.get(product_id=transaction.product_id)
    try:
        domain_name = transaction.__domain
    except AttributeError:
        domain_name = sql_product.domain

    try:
        sql_location = SQLLocation.objects.get(supply_point_id=transaction.case_id)
    except SQLLocation.DoesNotExist:
        sql_location = None

    try:
        state = StockState.include_archived.get(
            section_id=transaction.section_id,
            case_id=transaction.case_id,
            product_id=transaction.product_id,
        )
    except StockState.DoesNotExist:
        state = StockState(
            section_id=transaction.section_id,
            case_id=transaction.case_id,
            product_id=transaction.product_id,
            sql_product=sql_product,
            sql_location=sql_location,
        )

    # we may not be saving the latest transaction so make sure we use that
    # todo: this should change to server date
    latest_transaction = StockTransaction.latest(
        case_id=transaction.case_id,
        section_id=transaction.section_id,
        product_id=transaction.product_id
    )
    if latest_transaction != transaction:
        logging.warning(
            'Just fired signal for a stale stock transaction. Domain: {}, instance: {},latest was {}'.format(
                domain_name, transaction, latest_transaction
            )
        )
        transaction = latest_transaction
    state.last_modified_date = transaction.report.server_date
    state.last_modified_form_id = transaction.report.form_id
    state.stock_on_hand = transaction.stock_on_hand

    # so you don't have to look it up again in the signal receivers
    if domain_name:
        state.__domain = domain_name
    return state


def stock_state_deleted(instance):
    from corehq.apps.commtrack.models import StockState

    qs = StockTransaction.objects.filter(
        section_id=instance.section_id,
        case_id=instance.case_id,
        product_id=instance.product_id,
    ).order_by('-report__date')
    if qs:
        update_stock_state_for_transaction(qs[0])
    else:
        StockState.objects.filter(
            section_id=instance.section_id,
            case_id=instance.case_id,
            product_id=instance.product_id,
        ).delete()
