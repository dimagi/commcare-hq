from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import contextlib
import json
import time
from django.core.management.base import BaseCommand
from lxml import etree
import os
from corehq.apps.app_manager.dbaccessors import wrap_app
from io import open

try:
    from guppy import hpy
    track_perf = True
except ImportError:
    track_perf = False


_parser = etree.XMLParser(remove_blank_text=True)


def normalize_xml(xml):
    xml = etree.fromstring(xml, parser=_parser)
    return etree.tostring(xml, pretty_print=True)


@contextlib.contextmanager
def record_performance_stats(filepath, slug):
    hp = hpy()
    before = hp.heap()
    start = time.clock()
    try:
        yield
    finally:
        end = time.clock()
        after = hp.heap()
        leftover = after - before
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write('{},{},{}\n'.format(slug, leftover.size, end - start))


class Command(BaseCommand):
    help = """
        Pass in a path to a directory (dir, below) with the following layout:
        dir/
            src/
                [app-slug].json
                [app-slug].json
                ...
    """

    def add_arguments(self, parser):
        parser.add_argument('path')
        parser.add_argument('build_slug')

    def handle(self, path, build_slug, **options):
        app_slugs = []
        perfpath = os.path.join(path, '{}-performance.txt'.format(build_slug))
        if os.path.exists(perfpath):
            os.remove(perfpath)

        for name in os.listdir(os.path.join(path, 'src')):
            _JSON = '.json'
            if name.endswith(_JSON):
                app_slugs.append(name[:-len(_JSON)])

        for slug in app_slugs:
            print('Fetching %s...' % slug)
            source_path = os.path.join(path, 'src', '%s.json' % slug)
            with open(source_path, encoding='utf-8') as f:
                j = json.load(f)
                app = wrap_app(j)

            app.version = 1
            if not app.domain:
                app.domain = "test"
            build_path = os.path.join(path, build_slug, slug)
            print(' Creating files...')
            if track_perf:
                with record_performance_stats(perfpath, slug):
                    files = app.create_all_files()
            else:
                files = app.create_all_files()

            self.write_files(files, build_path)

    def write_files(self, files, path):
        for filename, payload in files.items():
            filepath = os.path.join(path, filename)
            dirpath, filename = os.path.split(filepath)
            try:
                os.makedirs(dirpath)
            except OSError:
                # file exists
                pass
            with open(filepath, 'w', encoding='utf-8') as f:
                if filepath.endswith('.xml'):
                    payload = normalize_xml(payload)
                f.write(payload)
