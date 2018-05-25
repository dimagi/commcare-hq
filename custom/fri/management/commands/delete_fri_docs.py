from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

from django.core.management.base import BaseCommand
from corehq.dbaccessors.couchapps.all_docs import get_doc_ids_by_class
from corehq.util.couch import iter_update, DocUpdate
from custom.fri.models import FRIMessageBankMessage, FRIRandomizedMessage, FRIExtraMessage

from six.moves import input


def delete_fn(doc):
    return DocUpdate(doc, delete=True)


class Command(BaseCommand):

    def handle(self, **options):
        for doc_class in [FRIMessageBankMessage, FRIRandomizedMessage, FRIExtraMessage]:
            ids = get_doc_ids_by_class(doc_class)

            msg = "Delete {} {} docs?\n(y/N)".format(len(ids), doc_class.__name__)
            if input(msg) == 'y':
                iter_update(doc_class.get_db(), delete_fn, ids, verbose=True)
