import cProfile
from unittest.mock import patch

from django.core.management import BaseCommand

from corehq.apps.ota.views import get_restore_response
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import get_complete_username
from corehq.util.dates import get_timestamp_for_filename

INTERPRET_PROFILE = """
If you're running this on a server, download locally by running

    $ ./manage.py get_download_url {filename}

May I suggest interpreting the file with

    $ pip install snakeviz
    $ snakeviz {filename}
"""


class FakeRequest:
    ...


class Command(BaseCommand):
    """Runs a profiled restore for the provided user"""

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('domain')
        parser.add_argument('--app_id')

    def handle(self, username, domain, **options):
        full_username = get_complete_username(username, domain)
        couch_user = CouchUser.get_by_username(full_username)
        app_id = options['app_id']

        filename = f'restore-{get_timestamp_for_filename()}.prof'
        profile = cProfile.Profile()
        with patch('corehq.util.quickcache.get_request', lambda: FakeRequest()):
            profile.enable()
            response, timing_context = get_restore_response(
                domain, couch_user, app_id=app_id, version="2.0"
            )
            profile.disable()
        profile.dump_stats(filename)

        timing_context.print()
        print(f"\nLogged restore profile to {filename}")
        print(INTERPRET_PROFILE.format(filename=filename))
