from __future__ import absolute_import
from __future__ import unicode_literals
from couchdbkit import ResourceNotFound
from django.core.management.base import BaseCommand
from casexml.apps.case.models import CommCareCase
from corehq.apps.commtrack.models import StockState
from corehq.apps.products.models import Product


class Command(BaseCommand):
    # context: https://github.com/dimagi/commcare-hq/pull/4043/files#diff-649db0a832878e7671cee114fa1e66b0R50
    help = 'Checks the state of products prior to migrating them to sql'

    def handle(self, **options):

        self.stdout.write("Processing products...\n")
        products = set()
        total = StockState.objects.count()
        failed = []
        for i, ss in enumerate(StockState.objects.all()):
            if i % 500 == 0:
                self.stdout.write('done {}/{}'.format(i, total))
            if ss.product_id not in products:
                try:
                    product = Product.get(ss.product_id)
                    assert product.doc_type == 'Product'
                    products.add(ss.product_id)
                except (ResourceNotFound, AssertionError):
                    try:
                        case = CommCareCase.get(ss.case_id)
                    except ResourceNotFound:
                        case = CommCareCase()
                    failed.append((ss, case))
        if failed:
            for ss, case in failed:
                self.stdout.write('No product with ID "{}" found! case ID: {}, domain {}'.format(
                    ss.product_id, ss.case_id, case.domain
                ))
            self.stderr.write('{}/{} stock states FAILED check'.format(len(failed), total))
