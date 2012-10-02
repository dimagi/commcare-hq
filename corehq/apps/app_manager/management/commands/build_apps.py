import json
from django.core.management.base import BaseCommand, CommandError
from lxml import etree
import os
from corehq.apps.app_manager.models import Application

_parser = etree.XMLParser(remove_blank_text=True)
def normalize_xml(xml):
    xml = etree.fromstring(xml, parser=_parser)
    return etree.tostring(xml, pretty_print=True)


class Command(BaseCommand):
    args = '<path_to_dir> <build-slug>'
    help = """
        Pass in a path to a directory (dir, below) with the following layout:
        dir/
            src/
                [app-slug].json
                [app-slug].json
                ...
    """
    def handle(self, *args, **options):
        path, build_slug = args

        app_slugs = []
        for name in os.listdir(os.path.join(path, 'src')):
            _JSON = '.json'
            if name.endswith(_JSON):
                app_slugs.append(name[:-len(_JSON)])

        for slug in app_slugs:
            print 'Fetching %s...' % slug
            source_path = os.path.join(path, 'src', '%s.json' % slug)
            with open(source_path) as f:
                app = Application.wrap(json.load(f))
            app.version = 1
            build_path = os.path.join(path, build_slug, slug)
            print ' Creating files...'
            self.create_files(app, build_path)

    def create_files(self, app, path):
        files = app.create_all_files()
        for filename, payload in files.items():
            print "  %s" % filename
            filepath = os.path.join(path, filename)
            dirpath, filename = os.path.split(filepath)
            try:
                os.makedirs(dirpath)
            except OSError:
                # file exists
                pass
            with open(filepath, 'w') as f:
                if filepath.endswith('.xml'):
                    payload = normalize_xml(payload)
                f.write(payload)