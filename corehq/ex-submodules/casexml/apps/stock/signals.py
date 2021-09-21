import logging
from casexml.apps.stock.models import StockTransaction


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

    sql_location = SQLLocation.objects.get_or_None(supply_point_id=transaction.case_id)

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
