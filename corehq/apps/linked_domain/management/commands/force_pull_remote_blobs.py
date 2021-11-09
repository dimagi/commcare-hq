from django.core.management import BaseCommand

from couchdbkit import ResourceNotFound

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.hqmedia.models import CommCareMultimedia
from corehq.apps.linked_domain.remote_accessors import fetch_remote_media
from corehq.apps.linked_domain.util import _add_domain_access


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('app_id')

    def handle(self, domain, app_id, **options):
        app = get_app(domain, app_id)
        try:
            remote_details = app.domain_link.remote_details
        except AttributeError:
            print("This command can only be run on remote linked apps")
            return

        missing_blobs = self.find_missing_blobs(app)
        if not missing_blobs:
            print("No missing multimedia found")
            return

        print(f"Attempting to fetch the following images from {remote_details.url_base}")
        print(",".join([blob[0] for blob in missing_blobs]))

        fetch_remote_media(app.domain, missing_blobs, remote_details)

    def find_missing_blobs(self, app):
        missing = []
        for path, media_info in app.multimedia_map.items():
            try:
                local_media = CommCareMultimedia.get(media_info['multimedia_id'])
                local_media.get_display_file()
            except ResourceNotFound:
                filename = path.split('/')[-1]
                missing.append((filename, media_info))
            else:
                _add_domain_access(app.domain, local_media)
        return missing
