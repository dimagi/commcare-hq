from optparse import make_option
from django.core.management.base import NoArgsCommand

from restkit.conn import Connection
from socketpool.pool import ConnectionPool
from pillowtop.run_pillowtop import start_pillows

class Command(NoArgsCommand):
    help = "Recompute diff properties on all model changes, and set next/prev pointers"
    option_list = NoArgsCommand.option_list + (
        make_option('--reset', action='store_true', dest='recompute',
            help='Recompute values.'),
    )
    def handle_noargs(self, **options):
        start_pillows()




