import os
from optparse import make_option

from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Clear supervisor confs for the given environment"
    args = "[user]"

    option_list = BaseCommand.option_list + (
        make_option('--conf_location', help='Supervisor configuration file path', default=None),
    )

    def handle(self, *args, **options):
        conf_dir = options['conf_location']
        environment = settings.SERVER_ENVIRONMENT
        files = os.listdir(conf_dir)
        env_confs = filter(lambda x: x.startswith('%s_' % environment) and x.endswith('.conf'), files)
        for c in env_confs:
            os.remove(os.path.join(conf_dir, c))

