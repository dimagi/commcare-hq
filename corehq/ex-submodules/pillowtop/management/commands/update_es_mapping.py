from copy import copy
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from corehq.elastic import get_es_new
from corehq.pillows.utils import get_all_expected_es_indices


class Command(BaseCommand):
    help = "Update an existing ES mapping. If there are conflicting changes this command will fail."
    args = "[INDEX NAME or ALIAS]"

    def handle(self, *args, **options):
        if len(args) != 1: raise CommandError("Please specify the index name to update")
        index_name = args[0]
        es_indices = list(get_all_expected_es_indices())
        indexes = [index for index in es_indices if index_name == index.alias or index_name == index.index]

        if not indexes:
            raise CommandError("No matching index found: {}".format(index_name))
        index_info = indexes[0]
        es = get_es_new()
        if _confirm("Confirm that you want to update the mapping for '{}'".format(index_info.index)):
            mapping = copy(index_info.mapping)
            mapping['_meta']['created'] = datetime.utcnow().isoformat()
            mapping_res = es.indices.put_mapping(index_info.type, {index_info.type: mapping}, index=index_info.index)
            if mapping_res.get('acknowledged', False):
                print "Index successfully updated"
            else:
                print mapping_res


def _confirm(message):
    if raw_input(
            '{} [y/n]'.format(message)
    ).lower() == 'y':
        return True
    else:
        raise CommandError('abort')
