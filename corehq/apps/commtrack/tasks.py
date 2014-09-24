from celery.task import task
from corehq.apps.commtrack.consumption import recalculate_domain_consumption
from corehq.apps.locations.bulk import import_locations
from corehq.apps.commtrack.bulk import import_products
from dimagi.utils.excel_importer import SingleExcelImporter, MultiExcelImporter


@task
def import_locations_async(domain, file_ref_id):
    importer = MultiExcelImporter(import_locations_async, file_ref_id)
    results = list(import_locations(domain, importer))
    importer.mark_complete()

    return {
        'messages': results
    }


@task
def import_products_async(domain, file_ref_id):
    importer = SingleExcelImporter(import_products_async, file_ref_id)
    results = list(import_products(domain, importer))
    importer.mark_complete()

    return {
        'messages': results
    }


@task
def recalculate_domain_consumption_task(domain):
    recalculate_domain_consumption(domain)