import os
from optparse import make_option

from django.core.management.base import BaseCommand
from django.conf import settings
import sys


class Command(BaseCommand):
    help = "Clear supervisor confs for the given environment"
    args = ""

    option_list = BaseCommand.option_list + (
        make_option('--conf_location', help='Supervisor configuration file path', default=None),
    )

    def handle(self, *args, **options):
        conf_dir = options['conf_location']
        environment = settings.SERVER_ENVIRONMENT
        if not os.path.exists(conf_dir):
            sys.exit("[clear_supervisor_confs] Error: the path %s is not reachable by this process" % conf_dir)
        files = os.listdir(conf_dir)
        env_confs = filter(lambda x: x.startswith('%s_' % environment) and x.endswith('.conf'), files)
        for c in env_confs:
            os.remove(os.path.join(conf_dir, c))
            print "\t[clear_supervisor_confs] Removed supervisor configuration file: %s" % c

