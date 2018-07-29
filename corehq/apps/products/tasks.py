from __future__ import absolute_import
from __future__ import unicode_literals
from celery.task import task
from corehq.apps.products.bulk import import_products
from corehq.util.workbook_json.excel_importer import SingleExcelImporter, UnknownFileRefException

from django.utils.translation import ugettext as _


@task
def import_products_async(domain, file_ref_id):
    try:
        importer = SingleExcelImporter(import_products_async, file_ref_id)
    except UnknownFileRefException:
        return {
            'messages': {
                'errors': [_("Sorry, something went wrong! Please try again and report an "
                             "issue if the problem persists")]
            }
        }

    results = import_products(domain, importer)
    importer.mark_complete()

    return {
        'messages': results
    }
