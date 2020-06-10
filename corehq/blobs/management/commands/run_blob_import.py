import tarfile

from django.core.management import BaseCommand

from corehq.blobs import get_blob_db

USAGE = "Usage: ./manage.py run_blob_import <filename>"


class Command(BaseCommand):
    help = USAGE

    def add_arguments(self, parser):
        parser.add_argument('filename')

    def handle(self, filename, **options):
        to_db = get_blob_db()
        with tarfile.open(filename, 'r:gz') as tgzfile:
            for tarinfo in tgzfile:
                key = tarinfo.name
                fileobj = tgzfile.extractfile(tarinfo)
                to_db.copy_blob(fileobj, key=key)
