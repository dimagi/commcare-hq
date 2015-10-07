from django.core.management.base import LabelCommand
import sys
from corehq.apps.domain.models import Domain


class Command(LabelCommand):
    help = "Purge ALL documents of a particular type. E.g. purge_docs MyDocType,AnotherOne"

    def handle(self, doc_types, *args, **options):

        input = raw_input('\n'.join([
            '\n\nReally delete documents of the following types: {}?',
            'This operation is not reversible. Enter a number N to delete the first '
            'N found, or type "delete all" to delete everything.',
            '',
        ]).format(doc_types))
        if input == 'delete all':
            remaining = None
        else:
            try:
                remaining = int(input)
            except ValueError:
                print 'aborting'
                sys.exit()

        doc_types = doc_types.split(',')
        deleted = 0

        # unfortunately the only couch view we have for this needs to go by domain
        # will be a bit slow
        domain_names = Domain.get_all_names()
        database = Domain.get_db()
        for domain in domain_names:
            for doc_type in doc_types:
                docs = [row['doc'] for row in database.view(
                    'domain/docs',
                    startkey=[domain, doc_type],
                    endkey=[domain, doc_type, {}],
                    reduce=False,
                    include_docs=True,
                )][:remaining]
                if docs:
                    count = len(docs)
                    print 'deleting {} {}s from {}'.format(count, doc_type, domain)
                    database.delete_docs(docs)
                    deleted += count
                    if remaining is not None:
                        remaining -= count
                        if remaining <= 0:
                            return

        print 'successfully deleted {} documents'.format(deleted)
