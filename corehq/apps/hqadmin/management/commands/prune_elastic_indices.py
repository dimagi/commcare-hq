from optparse import make_option
from django.conf import settings
from django.core.management import BaseCommand
from elasticsearch import Elasticsearch
from pillowtop import get_all_pillows
from pillowtop.listener import AliasedElasticPillow


class Command(BaseCommand):
    help = 'Delete all unreferenced elasticsearch indices.'

    option_list = BaseCommand.option_list + (
        make_option('--verbose', help='Additional logging.', action='store_true',
                    default=False),
        make_option('--noinput', help='Do not prompt user for input', action='store_true',
                    default=False),
    )

    def handle(self, *args, **options):
        es = Elasticsearch([{
            'host': settings.ELASTICSEARCH_HOST,
            'port': settings.ELASTICSEARCH_PORT,
        }])
        # call this before getting existing indices because apparently getting the pillow will create the index
        # if it doesn't exist
        found_indices = set(es.indices.get_aliases().keys())
        existing_indices = set(
            pillow.es_index for pillow in filter(lambda x: isinstance(x, AliasedElasticPillow), get_all_pillows())
        )

        if options['verbose']:
            if existing_indices - found_indices:
                print 'the following indices were not found:\n{}\n'.format(
                    '\n'.join(existing_indices - found_indices)
                )
            print 'expecting {} indices:\n{}\n'.format(len(existing_indices),
                                                       '\n'.join(sorted(existing_indices)))

        to_delete = set([index for index in found_indices if index not in existing_indices])
        if to_delete:
            if options['noinput'] or raw_input(
                    '\n'.join([
                        'Really delete ALL the unrecognized elastic indices?',
                        'Here are the indices that will be deleted:',
                        '\n'.join(sorted(to_delete)),
                        'This operation is not reversible and all data will be lost.',
                        'Type "delete indices" to continue:\n',
                    ])).lower() == 'delete indices':
                for index in to_delete:
                    es.indices.delete(index)
            else:
                print 'aborted'
        else:
            print 'no indices need pruning'
