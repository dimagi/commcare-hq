from celery.task import task
from corehq.apps.products.bulk import import_products
from corehq.util.spreadsheets.excel_importer import SingleExcelImporter


@task
def import_products_async(domain, file_ref_id):
    importer = SingleExcelImporter(import_products_async, file_ref_id)
    results = import_products(domain, importer)
    importer.mark_complete()

    return {
        'messages': results
    }
