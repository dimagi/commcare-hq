import cStringIO
import zipfile

from django.core.management.base import BaseCommand

from corehq.blobs import get_blob_db

USAGE = "Usage: ./manage.py import_blob_zip <zipname>"


class Command(BaseCommand):
    help = USAGE

    def add_arguments(self, parser):
        parser.add_argument('zipname')

    def handle(self, zipname, **options):
        from_zip = zipfile.ZipFile(zipname)

        to_db = get_blob_db()

        for filename in from_zip.namelist():
            bucket = '/'.join(filename.split('/')[:-1])
            identifier = filename.split('/')[-1]
            blob = cStringIO.StringIO(from_zip.read(filename))
            to_db.put(blob, identifier, bucket)
