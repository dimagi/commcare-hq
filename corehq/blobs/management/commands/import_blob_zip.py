import io
import zipfile
from inspect import cleandoc

from django.core.management.base import BaseCommand

from corehq.blobs import get_blob_db

USAGE = cleandoc("""
    Usage: ./manage.py import_blob_zip <zipname>

    NOTE:
        This command is for importing legacy blob export zip files.
        Blob exports created after June 2020 use tar.gz files. To import
        them, use the run_blob_import command:

            $ ./manage.py run_blob_import <filename>

""")


class Command(BaseCommand):
    help = USAGE

    def add_arguments(self, parser):
        parser.add_argument('zipname')

    def handle(self, zipname, **options):
        from_zip = zipfile.ZipFile(zipname)
        to_db = get_blob_db()
        for key in from_zip.namelist():
            blob = io.BytesIO(from_zip.read(key))
            to_db.copy_blob(blob, key=key)
