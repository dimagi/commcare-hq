from django.core.management.base import LabelCommand, CommandError
import sys
from optparse import make_option
import simplejson
from corehq.elastic import get_es
from pillowtop.listener import AliasedElasticPillow
from pillowtop.management.pillowstate import get_pillow_states
from pillowtop import get_all_pillows


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
        make_option('--flip_alias',
                    action='store',
                    dest='pillow_class',
                    default=None,
                    help="Single Pillow class to flip alias"),
        make_option('--list',
                    action='store_true',
                    dest='list_pillows',
                    default=False,
                    help="Print AliasedElasticPillows that can be operated on"),
        make_option('--info',
                    action='store_true',
                    dest='show_info',
                    default=True,
                    help="Debug printout of ES indices and aliases"),
        make_option('--code_red',
                    action='store_true',
                    dest='code_red',
                    default=False,
                    help="Code red! Delete all indices and pillow checkpoints and start afresh."),
    )

    def handle(self, *args, **options):
        if len(args) != 0: raise CommandError("This command doesn't expect arguments!")
        show_info = options['show_info']
        list_pillows = options['list_pillows']
        flip_all = options['flip_all']
        flip_single = options['pillow_class']
        code_red = options['code_red']
        es = get_es()

        pillows = get_all_pillows()
        aliased_pillows = filter(lambda x: isinstance(x, AliasedElasticPillow), pillows)

        if code_red:
            if raw_input('\n'.join([
                'CODE RED!!!',
                'Really delete ALL the elastic indices and pillow checkpoints?',
                'The following pillows will be affected:',
                '\n'.join([type(p).__name__ for p in aliased_pillows]),
                'This is a PERMANENT action. (Type "code red" to continue):',
                '',
            ])).lower() == 'code red':
                for pillow in aliased_pillows:
                    pillow.delete_index()
                    print 'deleted elastic index: {}'.format(pillow.es_index)
                    checkpoint_id = pillow.checkpoint_manager.checkpoint_id
                    if pillow.couch_db.doc_exist(checkpoint_id):
                        pillow.couch_db.delete_doc(checkpoint_id)
                        print 'deleted checkpoint: {}'.format(checkpoint_id)
            else:
                print 'Safety first!'
            return

        if show_info:
            get_pillow_states(aliased_pillows).dump_info()
        if list_pillows:
            print aliased_pillows
        if flip_all:
            for pillow in aliased_pillows:
                pillow.assume_alias()
            print simplejson.dumps(es.get('_aliases'), indent=4)
        if flip_single is not None:
            pillow_class_name = flip_single
            pillow_to_use = filter(lambda x: x.__class__.__name__ == pillow_class_name, aliased_pillows)
            if len(pillow_to_use) != 1:
                print "Unknown pillow (option --pillow <name>) class string, the options are: \n\t%s" % ', '.join(
                    [x.__class__.__name__ for x in aliased_pillows])
                sys.exit()

            target_pillow = pillow_to_use[0]
            target_pillow.assume_alias()
            print es.get('_aliases')
