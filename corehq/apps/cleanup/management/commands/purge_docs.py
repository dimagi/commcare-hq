from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
import sys
from corehq.apps.domain.models import Domain
from corehq.util.couch import get_db_by_doc_type
from six.moves import input


class Command(BaseCommand):
    help = "Purge ALL documents of a particular type. E.g. purge_docs MyDocType,AnotherOne"

    def handle(self, doc_types, *args, **options):

        user_input = input('\n'.join([
            '\n\nReally delete documents of the following types: {}?',
            'This operation is not reversible. Enter a number N to delete the first '
            'N found, or type "delete all" to delete everything.',
            '',
        ]).format(doc_types))
        if user_input == 'delete all':
            remaining = None
        else:
            try:
                remaining = int(user_input)
            except ValueError:
                print('aborting')
                sys.exit()

        doc_types = doc_types.split(',')
        deleted = 0

        # unfortunately the only couch view we have for this needs to go by domain
        # will be a bit slow
        domain_names = Domain.get_all_names()
        for doc_type in doc_types:
            db = get_db_by_doc_type(doc_type)
            if not db:
                print("Cannot find db for {}, skipping".format(doc_type))
                continue

            for domain in domain_names:
                docs = [row['doc'] for row in db.view(
                    'by_domain_doc_type_date/view',
                    startkey=[domain, doc_type],
                    endkey=[domain, doc_type, {}],
                    reduce=False,
                    include_docs=True,
                )][:remaining]
                if docs:
                    count = len(docs)
                    print('deleting {} {}s from {}'.format(count, doc_type, domain))
                    db.delete_docs(docs)
                    deleted += count
                    if remaining is not None:
                        remaining -= count
                        if remaining <= 0:
                            return

        print('successfully deleted {} documents'.format(deleted))
