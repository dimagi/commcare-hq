from celery.task import task
from corehq.apps.commtrack.consumption import recalculate_domain_consumption
from corehq.apps.locations.bulk import import_locations
from corehq.util.spreadsheets.excel_importer import MultiExcelImporter


@task
def import_locations_async(domain, file_ref_id):
    importer = MultiExcelImporter(import_locations_async, file_ref_id)
    results = list(import_locations(domain, importer))
    importer.mark_complete()

    return {
        'messages': results
    }


@task(ignore_result=True)
def recalculate_domain_consumption_task(domain):
    recalculate_domain_consumption(domain)
