from optparse import make_option
from django.core.management.base import NoArgsCommand

from restkit.conn import Connection
from socketpool.pool import ConnectionPool
from pillowtop.run_pillowtop import start_pillows

class Command(NoArgsCommand):
    help = "Run the pillowtop management command to scan all _changes feeds"
    option_list = NoArgsCommand.option_list + (
    )
    def handle_noargs(self, **options):
        start_pillows()




