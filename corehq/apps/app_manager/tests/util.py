from doctest import Example
import json
import os
from corehq.apps.builds.models import CommCareBuild
from lxml.doctestcompare import LXMLOutputChecker
import difflib


class TestFileMixin(object):

    file_path = ''

    @property
    def base(self):
        return os.path.join(os.path.dirname(__file__), *self.file_path)

    def get_file(self, name, ext):
        with open(os.path.join(self.base, '%s.%s' % (name, ext))) as f:
            return f.read()

    def get_json(self, name):
        return json.loads(self.get_file(name, 'json'))

    def get_xml(self, name):
        return self.get_file(name, 'xml')

    def assertXmlEqual(self, want, got):
        # snippet from http://stackoverflow.com/questions/321795/comparing-xml-in-a-unit-test-in-python/7060342#7060342
        checker = LXMLOutputChecker()
        if not checker.check_output(want, got, 0):
            message = "XML mismatch\n\n"
            for line in difflib.unified_diff(want.splitlines(1), got.splitlines(1), fromfile='want.xml', tofile='got.xml'):
                message += line + '\n'
            raise AssertionError(message)


def add_build(version, build_number):
    path = os.path.join(os.path.dirname(__file__), "jadjar")
    jad_path = os.path.join(path, 'CommCare_%s_%s.zip' % (version, build_number))
    CommCareBuild.create_from_zip(jad_path, version, build_number)
