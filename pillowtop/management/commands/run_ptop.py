from gevent import monkey; monkey.patch_all()
from django.core.management.base import NoArgsCommand

from pillowtop.run_pillowtop import start_pillows

class Command(NoArgsCommand):
    help = "Run all pillows listed in settings."
    option_list = NoArgsCommand.option_list + (
    )
    def handle_noargs(self, **options):
        start_pillows()




