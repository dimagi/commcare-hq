from celery.task import task
from django.core.cache import cache
from corehq.apps.commtrack.consumption import recalculate_domain_consumption
from soil import DownloadBase
from corehq.apps.locations.bulk import import_locations
from corehq.apps.commtrack.bulk import import_stock_reports, import_products
from soil.util import expose_download
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