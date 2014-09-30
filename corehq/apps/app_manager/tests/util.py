import json
import os
import lxml
from lxml.doctestcompare import LXMLOutputChecker
import mock
from corehq.apps.builds.models import CommCareBuild, CommCareBuildConfig, \
    BuildSpec
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

    def assertXmlEqual(self, expected, actual, normalize=True):
        if normalize:
            parser = lxml.etree.XMLParser(remove_blank_text=True)
            parse = lambda *args: normalize_attributes(lxml.etree.XML(*args))
            expected = lxml.etree.tostring(parse(expected, parser), pretty_print=True)
            actual = lxml.etree.tostring(parse(actual, parser), pretty_print=True)

        # snippet from http://stackoverflow.com/questions/321795/comparing-xml-in-a-unit-test-in-python/7060342#7060342
        checker = LXMLOutputChecker()
        if not checker.check_output(expected, actual, 0):
            message = "XML mismatch\n\n"
            diff = difflib.unified_diff(
                expected.splitlines(1),
                actual.splitlines(1),
                fromfile='want.xml',
                tofile='got.xml'
            )
            for line in diff:
                message += line
            raise AssertionError(message)


def normalize_attributes(xml):
    """Sort XML attributes to make it easier to find differences"""
    for node in xml.iterfind(".//*"):
        if node.attrib:
            attrs = sorted(node.attrib.iteritems())
            node.attrib.clear()
            node.attrib.update(attrs)
    return xml


def add_build(version, build_number):
    path = os.path.join(os.path.dirname(__file__), "jadjar")
    jad_path = os.path.join(path, 'CommCare_%s_%s.zip' % (version, build_number))
    return CommCareBuild.create_from_zip(jad_path, version, build_number)


def _get_default(self, application_version):
    if application_version == '1.0':
        return BuildSpec({
            "version": "1.2.1",
            "build_number": None,
            "latest": True
        })
    else:
        return BuildSpec({
            "version": "2.7.0",
            "build_number": None,
            "latest": True
        })

patch_default_builds = mock.patch.object(CommCareBuildConfig, 'get_default',
                                         _get_default)
