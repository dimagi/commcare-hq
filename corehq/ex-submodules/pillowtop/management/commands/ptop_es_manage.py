from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
import simplejson
from elasticsearch.exceptions import NotFoundError

from corehq.elastic import get_es_new
from corehq.pillows.utils import get_all_expected_es_indices
from pillowtop.es_utils import assume_alias
from six.moves import input
import six


class Command(BaseCommand):
    help = "."

    def add_arguments(self, parser):
        parser.add_argument(
            '--flip_all_aliases',
            action='store_true',
            dest='flip_all',
            default=False,
            help="Flip all aliases",
        )
        parser.add_argument(
            '--list',
            action='store_true',
            dest='list_pillows',
            default=False,
            help="Print AliasedElasticPillows that can be operated on",
        )
        parser.add_argument(
            '--code_red',
            action='store_true',
            dest='code_red',
            default=False,
            help="Code red! Delete all indices and pillow checkpoints and start afresh.",
        )

    def handle(self, **options):
        flip_all = options['flip_all']
        code_red = options['code_red']

        es = get_es_new()
        es_indices = list(get_all_expected_es_indices())
        if code_red:
            if input('\n'.join([
                'CODE RED!!!',
                'Really delete ALL the elastic indices and pillow checkpoints?',
                'The following indices will be affected:',
                '\n'.join([six.text_type(index_info) for index_info in es_indices]),
                'This is a PERMANENT action. (Type "code red" to continue):',
                '',
            ])).lower() == 'code red':
                for index_info in es_indices:
                    try:
                        es.indices.delete(index_info.index)
                    except NotFoundError:
                        print('elastic index not present: {}'.format(index_info.index))
                    else:
                        print('deleted elastic index: {}'.format(index_info.index))
            else:
                print('Safety first!')
            return

        if flip_all:
            for index_info in es_indices:
                assume_alias(es, index_info.index, index_info.alias)
            print(simplejson.dumps(es.indices.get_alias(), indent=4))
