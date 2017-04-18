from optparse import make_option

from django.core.management import BaseCommand

from corehq.apps.commtrack.models import CommtrackConfig


class Command(BaseCommand):
    args = '<domain domain ...>'
    help = 'Temporary command to update specific commtrack settings for a list of domains.'

    option_list = BaseCommand.option_list + (
        make_option(
            '--setting-name', choices=['sync_consumption_fixtures', 'use_auto_consumption'],
            help='Setting to change'
        ),
        make_option(
            '--value', choices=['1', '0', 'true', 'false'], help='The value to set.'
        ),
    )

    def handle(self, *domains, **options):
        setting = options['setting_name']
        value = options['value'] == '1' or options['value'] == 'true'
        for domain in domains:
            config = CommtrackConfig.for_domain(domain)
            if not config:
                print "Skipping domain '{}', no config".format(domain)
                continue

            current_value = getattr(config, setting)
            if current_value == value:
                print "Skipping domain '{}', '{}' already set to '{}'".format(domain, setting, value)
            else:
                print "Changing value of '{}' for domain '{}' to '{}'".format(setting, domain, value)
                setattr(config, setting, value)
                config.save()
