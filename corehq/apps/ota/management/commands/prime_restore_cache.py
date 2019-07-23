from __future__ import absolute_import, unicode_literals

from django.core.management.base import BaseCommand

from corehq.apps.ota.views import get_restore_response
from corehq.apps.users.models import CommCareUser
from corehq.const import ONE_DAY


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('file_path')

    def handle(self, **options):
        file_path = options['file_path']
        with open(file_path, 'r') as f:
            for u in f:
                try:
                    username = u.rstrip()
                    couch_user = CommCareUser.get_by_username(username)
                    device_id = couch_user.last_device.device_id
                    app_id = couch_user.last_device.app_meta[0].build_id
                    get_restore_response(
                        'icds-cas',
                        couch_user,
                        app_id,
                        device_id=device_id,
                        version='2.0',
                        force_cache=True,
                        cache_timeout=ONE_DAY
                    )
                except Exception as e:
                    print(e)
                else:
                    print(username)
