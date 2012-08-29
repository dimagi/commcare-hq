import os
from django.core.management.base import LabelCommand
from django.contrib.staticfiles import finders

class Command(LabelCommand):
    help = "Prints the paths of all the static files"

    def handle(self, *args, **options):
        prefix = os.getcwd()
        bootstrap_less = ["hq-bootstrap/less/hq-bootstrap.less",
                          "hq-bootstrap/less/formdesigner-old/formdesigner.less",
                          "hq-bootstrap/less/formdesigner-old/screen.less",
                          "hq-bootstrap/less/old/core.less",
                          "hq-bootstrap/less/old/app_manager.less"]
        bootstrap_js = ["hq-bootstrap/js/bootstrap.js",
                        "hq-bootstrap/js/bootstrap.min.js"]
        bootstrap_includes = {"submodules/hq-bootstrap/img": "hq-bootstrap/img/",
                              "submodules/hq-bootstrap/js/includes": "hq-bootstrap/js/",
                              "submodules/hq-bootstrap/js/includes/google-code-prettify": "hq-bootstrap/js/google-code-prettify/"}
        
        print r'echo "resource_versions = {"'
        for finder in finders.get_finders():
            for path, storage in finder.list(['.*', '*~', '* *']):
                if not storage.location.startswith(prefix):
                    continue
                url = os.path.join(storage.prefix, path) if storage.prefix else path
                parts = (storage.location + '/' + path).split('/')
                self.generate_output(url, parts)

        # Deal with Bootstrap Less files
        for less_file in bootstrap_less:
            exact_location = os.path.join(prefix, "submodules/"+less_file)
            parts = exact_location.split('/')
            self.generate_output(less_file, parts, dir_version=bool(less_file == bootstrap_less[0]))

        # Deal with primary Bootstrap javascript files
        for js_file in bootstrap_js:
            exact_location = os.path.join(prefix, "submodules/"+js_file)
            parts = exact_location.split('/')
            self.generate_output(js_file, parts, True)

        # Deal with Bootstrap image files
        for path, searched_url in bootstrap_includes.items():
            full_path = os.path.join(prefix, path)
            self.generate_output_for_dir(full_path, searched_url)

        print r'echo "}"'

    @staticmethod
    def generate_output(url, parts, dir_version=False):
        filepath = '/'.join(parts[:-1]) + '/'
        filename = parts[-1] if not dir_version else "."
        print r'filepath="%s"; filename="%s"; url="%s"' % (filepath, filename, url)
        print r"""cd $filepath; git log -n 1 --format=format:"    \"$url\": \"%h\"," $filename; echo"""


    def generate_output_for_dir(self, directory, prefix):
        for out_file in os.listdir(directory):
            exact_location = os.path.join(directory, out_file)
            parts = exact_location.split('/')
            self.generate_output(prefix+out_file, parts)
