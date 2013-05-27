from django.core.management.base import LabelCommand, CommandError
import sys
from optparse import make_option
import simplejson
from corehq.elastic import get_es
from pillowtop.listener import AliasedElasticPillow
from pillowtop.management.pillowstate import get_pillow_states
from pillowtop.run_pillowtop import import_pillows


class Command(LabelCommand):
    help = "."
    args = ""
    label = ""

    option_list = LabelCommand.option_list + \
                  (
                      make_option('--flip_aliases',
                                  action='store_true',
                                  dest='do_flip',
                                  default=False,
                                  help="Do the actual alias flip"),
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
                  )

    def handle(self, *args, **options):
        print args
        print options
        if len(args) != 0: raise CommandError("This command doesn't expect arguments!")

        print ""
        show_info = options['show_info']
        list_pillows = options['list_pillows']
        do_flip = options['do_flip']
        es = get_es()

        pillows = import_pillows()
        aliased_pillows = filter(lambda x: isinstance(x, AliasedElasticPillow), pillows)

        if show_info:
            print "\n\tHQ ES Index Alias Mapping Status"
            mapped_masters, unmapped_masters, stale_indices = get_pillow_states(pillows)

            print "\t## Current ES Indices in Source Control ##"
            for m in mapped_masters:
                print "\t\t%s => %s [OK]" % (m[0], m[1])

            print "\t## Current ES Indices in Source Control needing preindexing ##"
            for m in unmapped_masters:
                print "\t\t%s != %s [Run ES Preindex]" % (m[0], m[1])

            print "\t## Stale indices on ES ##"
            for m in stale_indices:
                print "\t\t%s: %s" % (m[0], "Holds [%s]" % ','.join(m[1]) if len(m[1]) > 0 else "No Alias, stale")
            print "done"
        if list_pillows:
            print aliased_pillows

        if do_flip:
            aliased_pillows = filter(lambda x: isinstance(x, AliasedElasticPillow), pillows)
            for pillow in aliased_pillows:
                pillow.assume_alias()

            print simplejson.dumps(es.get('_aliases'), indent=4)











