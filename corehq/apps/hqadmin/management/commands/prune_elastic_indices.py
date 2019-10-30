from django.core.management import BaseCommand

from corehq.elastic import get_es_new
from corehq.pillows.utils import get_all_expected_es_indices
from corehq.util.es import AuthorizationException


class Command(BaseCommand):
    help = 'Close all unreferenced elasticsearch indices.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            default=False,
            help='Additional logging.',
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            default=False,
            help='Do not prompt user for input',
        )
        parser.add_argument(
            '--delete',
            action='store_true',
            default=False,
            help='Delete the indices',
        )

    def handle(self, **options):
        es = get_es_new()
        # call this before getting existing indices because apparently getting the pillow will create the index
        # if it doesn't exist
        # fixme: this can delete real indices if a reindex is in progress
        found_indices = set(es.indices.get_aliases().keys())
        expected_indices = {info.index for info in get_all_expected_es_indices()}
        print(expected_indices)

        if options['verbose']:
            if expected_indices - found_indices:
                print('the following indices were not found:\n{}\n'.format(
                    '\n'.join(expected_indices - found_indices)
                ))
            print('expecting {} indices:\n{}\n'.format(len(expected_indices),
                                                       '\n'.join(sorted(expected_indices))))

        unref_indices = set([index for index in found_indices if index not in expected_indices])
        if unref_indices:
            if options['delete']:
                _delete_indices(es, unref_indices)
            else:
                _close_indices(es, unref_indices, options['noinput'])
        else:
            print('no indices need pruning')


def _delete_indices(es, to_delete):
    # always ask for confirmation when doing irreversible things
    if input(
            '\n'.join([
                'Really delete ALL the unrecognized elastic indices?',
                'Here are the indices that will be deleted:',
                '\n'.join(sorted(to_delete)),
                'This operation is not reversible and all data will be lost.',
                'Type "delete indices" to continue:\n',
            ])).lower() == 'delete indices':
        for index in to_delete:
            try:
                es.indices.flush(index)
            except AuthorizationException:
                # already closed
                pass
            es.indices.delete(index)
    else:
        print('aborted')


def _close_indices(es, to_close, noinput):
    if noinput or input(
            '\n'.join([
                'Really close ALL the unrecognized elastic indices?',
                'Here are the indices that will be closed:',
                '\n'.join(sorted(to_close)),
                'This operation is totally reversible but some downtime occur',
                'Type "close indices" to continue:\n',
            ])).lower() == 'close indices':
        for index in to_close:
            try:
                es.indices.flush(index)
            except AuthorizationException:
                # already closed
                pass
            es.indices.close(index)
    else:
        print('aborted')
