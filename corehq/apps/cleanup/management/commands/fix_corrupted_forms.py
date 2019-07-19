# encoding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

from django.core.management import BaseCommand

from six.moves import input

from corehq.apps.app_manager.dbaccessors import get_apps_by_id

SUSPICIOUS_STRINGS = [
    international_character.encode('utf-8').decode('latin1')
    for international_character in [
        'á', 'é', 'í', 'ó', 'ú',
        'Á', 'É', 'Í', 'Ó', 'Ú',
        '’',
    ] # TODO - add more common non-ascii characters
]


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('app_id')
        parser.add_argument('form_id')
        parser.add_argument(
            '--cleanup',
            action='store_true',
            dest='cleanup',
            default=False,
        )

    # https://dimagi-dev.atlassian.net/browse/HI-747
    def handle(self, domain, app_id, form_id, cleanup=False, **options):
        app = get_apps_by_id(domain, app_id)[0]
        form = app.get_form(form_id)
        source = form.source
        if any(suspicious_string in source for suspicious_string in SUSPICIOUS_STRINGS):
            print('FORM CONTAINS SUSPICIOUS STRING')
            if cleanup:
                if 'y' == input('Did you confirm that there are no app updates to publish? [y/N]'):
                    print('Cleaning form...')
                    form.source = source.encode('latin1').decode('utf-8')
                    app.save()
                    print('Done.')
                else:
                    print('Aborting...')
