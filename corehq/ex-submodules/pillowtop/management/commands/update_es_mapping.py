from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from copy import copy
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from corehq.elastic import get_es_new
from corehq.pillows.utils import get_all_expected_es_indices
from six.moves import input


class Command(BaseCommand):
    help = "Update an existing ES mapping. If there are conflicting changes this command will fail."

    def add_arguments(self, parser):
        parser.add_argument(
            'index_name',
            help='INDEX NAME or ALIAS',
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            dest='noinput',
            default=False,
            help='Skip important confirmation warnings.'
        )

    def handle(self, index_name, **options):
        noinput = options.pop('noinput')
        es_indices = list(get_all_expected_es_indices())
        indexes = [index for index in es_indices if index_name == index.alias or index_name == index.index]

        if not indexes:
            raise CommandError("No matching index found: {}".format(index_name))
        index_info = indexes[0]
        es = get_es_new()
        if (noinput or _confirm("Confirm that you want to update the mapping for '{}'".format(index_info.index))):
            mapping = copy(index_info.mapping)
            mapping['_meta']['created'] = datetime.utcnow().isoformat()
            mapping_res = es.indices.put_mapping(index_info.type, {index_info.type: mapping}, index=index_info.index)
            if mapping_res.get('acknowledged', False):
                print("Index successfully updated")
            else:
                print(mapping_res)


def _confirm(message):
    if input(
            '{} [y/n]'.format(message)
    ).lower() == 'y':
        return True
    else:
        raise CommandError('abort')
