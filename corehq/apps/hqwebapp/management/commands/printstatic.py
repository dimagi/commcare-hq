import os
from django.core.management.base import LabelCommand
from django.contrib.staticfiles import finders

class Command(LabelCommand):
    help = "Prints the paths of all the static files"

    def handle(self, *args, **options):
        prefix = os.getcwd()
        print r'echo "resource_versions = {"'
        for finder in finders.get_finders():
            for path, storage in finder.list(['.*', '*~', '* *']):
                if not storage.location.startswith(prefix):
                    continue
                url = os.path.join(storage.prefix, path) if storage.prefix else path
                parts = (storage.location + '/' + path).split('/')
                filepath = '/'.join(parts[:-1]) + '/'
                filename = parts[-1]
                print r'filepath="%s"; filename="%s"; url="%s"' % (filepath, filename, url)
                print r"""cd $filepath; git log -n 1 --format=format:"    \"$url\": \"%h\"," $filename; echo"""
        print r'echo "}"'