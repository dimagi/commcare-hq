from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management import BaseCommand

from corehq.apps.users.models import CommCareUser
from casexml.apps.phone.restore import RestoreParams, RestoreCacheSettings, RestoreConfig
from casexml.apps.case.xml import V2
from dimagi.utils.decorators.profile import resident_set_size


class Command(BaseCommand):
    """Prints out the memory allocated to this thread before and after a restore
    operation. Used to debug:
    http://manage.dimagi.com/default.asp?223540#1142280 and
    http://manage.dimagi.com/default.asp?225944#1142206

    Usage: ./manage.py mem_profile_restore large_caseload@domain.commcarehq.org
    """
    def add_arguments(self, parser):
        parser.add_argument('username')

    def handle(self, username, **options):
        couch_user = CommCareUser.get_by_username(username)
        project = couch_user.project

        restore_config = RestoreConfig(
            project=project,
            restore_user=couch_user.to_ota_restore_user(),
            params=RestoreParams(
                version=V2,
                include_item_count=True,
            ),
            cache_settings=RestoreCacheSettings(
                force_cache=True,
                cache_timeout=1,
                overwrite_cache=False,
            )
        )

        with resident_set_size():
            restore_config.get_payload()
