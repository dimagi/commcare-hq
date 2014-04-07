from celery.task import task
from django.core.cache import cache
from soil import DownloadBase
from corehq.apps.locations.bulk import import_locations
from corehq.apps.commtrack.bulk import import_stock_reports, import_products
from soil.util import expose_download
from dimagi.utils.excel import WorkbookJSONReader


@task
def import_locations_async(domain, file_ref_id):
    task = import_locations_async

    DownloadBase.set_progress(task, 0, 100)
    download_ref = DownloadBase.get(file_ref_id)
    workbook = WorkbookJSONReader(download_ref.get_filename())
    worksheets = workbook.worksheets

    results = list(import_locations(domain, worksheets, task))

    DownloadBase.set_progress(task, 100, 100)

    return {
        'messages': results
    }


@task
def import_stock_reports_async(download_id, domain, file_ref_id):
    """
    Same idea but for stock reports
    """
    download_ref = DownloadBase.get(file_ref_id)
    with open(download_ref.get_filename(), 'rb') as f:
        try:
            results = import_stock_reports(domain, f)
        except Exception, e:
            results = "ERROR: %s" % e
    ref = expose_download(results, 60*60*3, mimetype='text/csv')
    cache.set(download_id, ref)

@task
def import_products_async(domain, file_ref_id):
    task = import_products_async
    DownloadBase.set_progress(task, 0, 100)
    download_ref = DownloadBase.get(file_ref_id)
    results = import_products(domain, download_ref, task)
    DownloadBase.set_progress(task, 100, 100)
    return {
        'messages': results
    }
