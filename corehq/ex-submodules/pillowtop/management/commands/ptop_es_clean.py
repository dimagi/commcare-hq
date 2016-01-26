from django.core.management.base import BaseCommand

from corehq.elastic import get_es_new
from pillowtop import get_all_pillow_instances
from pillowtop.listener import AliasedElasticPillow


class Command(BaseCommand):
    help = "List all ES indexes that aren't being used and optionally delete them."
    args = ""
    label = ""

    def handle(self, *args, **options):
        es = get_es_new()

        pillows = get_all_pillow_instances()
        aliased_pillows = filter(lambda x: isinstance(x, AliasedElasticPillow), pillows)

        all_indexes = es.indices.get_aliases()
        for pillow in aliased_pillows:
            index = pillow.es_index
            all_indexes.pop(index, None)

        print('\n\nIndexes available for deletion:')

        index_names = []
        for index, data in all_indexes.items():
            aliases = ','.join(data['aliases'].keys())
            print('  * {} ({})'.format(index, aliases))
            index_names.append(index)

        if not index_names:
            print("No indexes available to delete.")
            return

        to_delete = raw_input("Type the names of the indexes you want to delete (separated by a comma):\n")
        if not to_delete:
            return

        def check_name(name):
            name = name.strip()
            if name not in index_names:
                print('{} not a valid index name'.format(name))
                return None
            return name

        to_delete = [check_name(name) for name in to_delete.split(',')]
        to_delete = filter(None, to_delete)
        for index in to_delete:
            delete = raw_input("Are you sure you want to delete '{}'? [y/n]".format(index))
            if delete == 'y':
                es.indices.delete(index)
