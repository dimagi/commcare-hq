from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete
from casexml.apps.case.models import CommCareCase
from casexml.apps.stock.consumption import compute_daily_consumption
from casexml.apps.stock.models import StockTransaction, DocDomainMapping
from corehq.apps.commtrack.models import StockState
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct


@receiver(post_save, sender=StockTransaction)
def update_stock_state_signal_catcher(sender, instance, *args, **kwargs):
    update_stock_state_for_transaction(instance)


def update_stock_state_for_transaction(txn):
    # todo: in the worst case, this function makes
    # - three calls to couch (for the case, domain, and commtrack config)
    # - three postgres queries (product, location, and state)
    # - one postgres write (to save the state)
    # and that doesn't even include the consumption calc, which can do a whole
    # bunch more work and hit the database.
    try:
        domain_name = txn.domain
    except AttributeError:
        domain_name = CommCareCase.get(txn.case_id).domain

    domain = Domain.get_by_name(domain_name)

    sql_product = SQLProduct.objects.get(product_id=txn.product_id)

    try:
        sql_location = SQLLocation.objects.get(supply_point_id=txn.case_id)
    except SQLLocation.DoesNotExist:
        sql_location = None

    try:
        state = StockState.include_archived.get(
            section_id=txn.section_id,
            case_id=txn.case_id,
            product_id=txn.product_id,
        )
    except StockState.DoesNotExist:
        state = StockState(
            section_id=txn.section_id,
            case_id=txn.case_id,
            product_id=txn.product_id,
            sql_product=sql_product,
            sql_location=sql_location,
        )

    state.last_modified_date = txn.report.date
    state.stock_on_hand = txn.stock_on_hand

    if domain and domain.commtrack_settings:
        consumption_calc = domain.commtrack_settings.get_consumption_config()
    else:
        consumption_calc = None

    state.daily_consumption = compute_daily_consumption(
        txn.case_id,
        txn.product_id,
        txn.report.date,
        'stock',
        consumption_calc
    )
    # so you don't have to look it up again in the signal receivers
    if domain:
        state.domain = domain.name
    state.save()


@receiver(post_delete, sender=StockTransaction)
def stock_state_deleted(sender, instance, *args, **kwargs):
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


@receiver(post_save, sender=StockState)
def update_domain_mapping(sender, instance, *args, **kwargs):
    case_id = unicode(instance.case_id)
    try:
        domain_name = instance.domain
        if not domain_name:
            raise ValueError()
    except (AttributeError, ValueError):
        domain_name = CommCareCase.get(case_id).domain
    if not DocDomainMapping.objects.filter(doc_id=case_id).exists():
        mapping = DocDomainMapping(
            doc_id=case_id,
            doc_type='CommCareCase',
            domain_name=domain_name,
        )
        mapping.save()
