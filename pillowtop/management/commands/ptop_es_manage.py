from django.core.management.base import LabelCommand, CommandError
import sys
from optparse import make_option
from corehq.elastic import get_es
from pillowtop.listener import AliasedElasticPillow
from pillowtop.run_pillowtop import import_pillows


class Command(LabelCommand):
    help = "."
    args = ""
    label = ""

    option_list = LabelCommand.option_list + \
                  (
                      make_option('--flip_alias',
                                  action='store_true',
                                  dest='do_flip',
                                  default=False,
                                  help="Do the actual alias flip"),
                      make_option('--pillow',
                                  action='store',
                                  dest='pillow_class',
                                  default=None,
                                  help="Pillow class to flip alias for [required with --flip_alias]"),
                      make_option('--list',
                                  action='store_true',
                                  dest='list_pillows',
                                  default=False,
                                  help="Print AliasedElasticPillows that can be operated on"),
                      make_option('--info',
                                  action='store_true',
                                  dest='show_info',
                                  default=False,
                                  help="Debug printout of ES indices and aliases"),


                  )

    def handle(self, *args, **options):
        if len(args) != 0: raise CommandError("This command doesn't expect arguments!")

        print ""
        show_info = options['show_info']
        list_pillows = options['list_pillows']
        do_flip = options['do_flip']
        es = get_es()

        pillows = import_pillows()
        aliased_pillows = filter(lambda x: isinstance(x, AliasedElasticPillow), pillows)

        #make tuples of (index, alias)
        #this maybe problematic if we have multiple pillows pointing to the same alias or indices
        master_aliases = dict((x.es_index, x.es_alias) for x in aliased_pillows)
        print master_aliases

        if show_info:
            system_status = es.get('_status')
            indices = system_status['indices'].keys()
            print ""
            print "\tActive indices"
            for index in indices:
                print "\t\t%s" % index
            print ""

            print "\n\tAlias Mapping Status"
            active_aliases = es.get('_aliases')
            for idx, alias_dict in active_aliases.items():
                line = ["\t\t", idx]
                is_master = False
                if idx in master_aliases:
                    is_master = True
                    line.append('*HEAD')

                if is_master:
                    if master_aliases[idx] in alias_dict['aliases']:
                        #is master, has alias, good
                        line.append('=> %s :)' % master_aliases[idx])
                    else:
                        #is not master, doesn't have alias, bad
                        line.append('=> Does not have alias yet :(')
                else:
                    #not a master index
                    line.append(
                        '=> [%s] Non HEAD has alias' % (' '.join(alias_dict['aliases'].keys())))
                print ' '.join(line)

            print ""
            sys.exit()
        if list_pillows:
            print aliased_pillows
            sys.exit()

        if do_flip:
            pillow_class_name = options['pillow_class']
            pillow_to_use = filter(lambda x: x.__class__.__name__ == pillow_class_name,
                                   aliased_pillows)
            if len(pillow_to_use) != 1:
                print "Unknown pillow (option --pillow <name>) class string, the options are: \n\t%s" % ', '.join(
                    [x.__class__.__name__ for x in aliased_pillows])
                sys.exit()

            #ok we got the pillow
            target_pillow = pillow_to_use[0]
            target_pillow.assume_alias()

            print es.get('_aliases')











