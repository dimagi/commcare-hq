from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

from django.core.management.base import BaseCommand, CommandError

from corehq.elastic import get_es_new
from corehq.pillows.utils import get_all_expected_es_indices
from six.moves import input


class Command(BaseCommand):
    help = "Update dynamic settings for existing elasticsearch indices."

    def add_arguments(self, parser):
        parser.add_argument(
            '--noinput',
            action='store_true',
            dest='noinput',
            default=False,
            help='Skip important confirmation warnings.'
        )

    def handle(self, **options):
        noinput = options.pop('noinput')
        es_indices = list(get_all_expected_es_indices())

        to_update = []
        es = get_es_new()

        for index_info in es_indices:
            old_settings = es.indices.get_settings(index=index_info.index)
            old_number_of_replicas = int(
                old_settings[index_info.index]['settings']['index']['number_of_replicas']
            )
            new_number_of_replicas = index_info.meta['settings']['number_of_replicas']

            if old_number_of_replicas != new_number_of_replicas:
                print("{} [{}]:\n  Number of replicas changing from {!r} to {!r}".format(
                    index_info.alias, index_info.index, old_number_of_replicas, new_number_of_replicas))
                to_update.append((index_info, {
                    'number_of_replicas': new_number_of_replicas,
                }))

        if not to_update:
            print("There is nothing to update.")
            return
        if (noinput or _confirm(
                "Confirm that you want to update all the settings above?")):
            for index_info, settings in to_update:
                    mapping_res = es.indices.put_settings(index=index_info.index, body=settings)
                    if mapping_res.get('acknowledged', False):
                        print("{} [{}]:\n  Index settings successfully updated".format(
                            index_info.alias, index_info.index))
                    else:
                        print(mapping_res)


def _confirm(message):
    if input(
            '{} [y/n]'.format(message)
    ).lower() == 'y':
        return True
    else:
        raise CommandError('abort')
