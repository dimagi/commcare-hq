from django.core.management.base import LabelCommand, CommandError
from optparse import make_option
import simplejson
from corehq.elastic import get_es_new
from corehq.pillows.utils import get_all_expected_es_indices
from pillowtop.es_utils import assume_alias


class Command(LabelCommand):
    help = "."
    args = ""
    label = ""

    option_list = LabelCommand.option_list + (
        make_option('--flip_all_aliases',
                    action='store_true',
                    dest='flip_all',
                    default=False,
                    help="Flip all aliases"),
        make_option('--list',
                    action='store_true',
                    dest='list_pillows',
                    default=False,
                    help="Print AliasedElasticPillows that can be operated on"),
        make_option('--code_red',
                    action='store_true',
                    dest='code_red',
                    default=False,
                    help="Code red! Delete all indices and pillow checkpoints and start afresh."),
    )

    def handle(self, *args, **options):
        if len(args) != 0: raise CommandError("This command doesn't expect arguments!")
        flip_all = options['flip_all']
        code_red = options['code_red']

        es = get_es_new()
        es_indices = list(get_all_expected_es_indices())
        if code_red:
            if raw_input('\n'.join([
                'CODE RED!!!',
                'Really delete ALL the elastic indices and pillow checkpoints?',
                'The following indices will be affected:',
                '\n'.join([unicode(index_info) for index_info in es_indices]),
                'This is a PERMANENT action. (Type "code red" to continue):',
                '',
            ])).lower() == 'code red':
                for index_info in es_indices:
                    es.indices.delete(index_info.index)
                    print 'deleted elastic index: {}'.format(index_info.index)
            else:
                print 'Safety first!'
            return

        if flip_all:
            for index_info in es_indices:
                assume_alias(es, index_info.index, index_info.alias)
            print simplejson.dumps(es.indices.get_aliases(), indent=4)
