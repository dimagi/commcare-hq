from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from casexml.apps.stock.models import StockReport, StockTransaction, DocDomainMapping
from corehq.apps.products.models import SQLProduct
from phonelog.models import DeviceReportEntry


def copy_postgres_data_for_docs(remote_postgres_slug, doc_ids, simulate=False):
    """
    Copies a set of data associated with a list of doc-ids from a remote postgres
    database to the locally configured one.
    """

    # can make this more configurable or less hard coded eventually
    # also note that ordering here is important for foreign key dependencies

    postgres_models = [
        (SQLProduct, 'product_id'),
        (StockReport, 'form_id'),
        (StockTransaction, 'case_id'),
        (DocDomainMapping, 'doc_id'),
        # StockState objects are "derived" and get created by StockTransaction post_save signal.
        # We may want to directly port these over in the future.
        # (StockState, 'case_id'),
        (DeviceReportEntry, 'xform_id'),
    ]
    for model, doc_field in postgres_models:
        query_set = model.objects.using(remote_postgres_slug).filter(
            **{'{}__in'.format(doc_field): doc_ids}
        )
        count = query_set.count()
        print("Copying {} models ({})".format(model.__name__, count))
        if not simulate:
            for i, item in enumerate(query_set):
                # this can cause primary key conflicts to overwrite local data I think. Oh well?
                item.save(using='default')
                print('Synced {}/{} {}'.format(i + 1, count, model.__name__))

