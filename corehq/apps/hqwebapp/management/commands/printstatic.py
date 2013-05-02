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
                self.generate_output(url, parts)
        print r'echo "}"'

    @staticmethod
    def generate_output(url, parts, dir_version=False):
        filepath = '/'.join(parts[:-1]) + '/'
        filename = parts[-1] if not dir_version else "."
        print r'FILEPATH="%s"; filename="%s"; url="%s"' % (filepath, filename, url)
        print r"""cd $FILEPATH; git log -n 1 --format=format:"    \"$url\": \"%h\"," $filename; echo"""


    def generate_output_for_dir(self, directory, prefix):
        for out_file in os.listdir(directory):
            exact_location = os.path.join(directory, out_file)
            parts = exact_location.split('/')
            self.generate_output(prefix+out_file, parts)
