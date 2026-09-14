from decimal import Decimal
import datetime
import tempfile
from pathlib import Path

import pytest
from django.test import SimpleTestCase
from lxml import etree

from ..xml_utils import XML, get_safe_xml_parser, safe_fromstring, serialize


class XMLSerializeTest(SimpleTestCase):

    def test_number_serialization(self):
        value = 1
        self.assertTrue(isinstance(value, int))
        self.assertEqual(serialize(value), '1')

        value = 0.004
        self.assertTrue(isinstance(value, float))
        self.assertEqual(serialize(value), '0.004')

        value = Decimal('100')
        self.assertTrue(isinstance(value, Decimal))
        self.assertEqual(serialize(value), '100')

    def test_string_serialization(self):
        self.assertEqual(serialize('ben'), 'ben')

    def test_none_serialization(self):
        self.assertEqual(serialize(None), '')

    def test_long_serialization(self):
        self.assertEqual(serialize(123), '123')

    def test_date_serialization(self):
        self.assertEqual(serialize(datetime.date(1982, 5, 14)), '1982-05-14')

    def test_datetime_serialization(self):
        self.assertEqual(serialize(datetime.datetime(2001, 1, 1, 12, 30, 45)), '2001-01-01T12:30:45.000000Z')

    def test_time_serialization(self):
        self.assertEqual(serialize(datetime.time(12, 4, 30)), '12:04:30')


def test_safe_fromstring_parses_normal_xml():
    root = safe_fromstring(b'<root><child>value</child></root>')
    assert root.find('child').text == 'value'


def test_safe_fromstring_accepts_str_input():
    root = safe_fromstring('<root>é</root>')
    assert root.text == 'é'


def test_safe_fromstring_parses_benign_doctype():
    root = safe_fromstring(b'<!DOCTYPE root []><root>hello</root>')
    assert root.text == 'hello'


def test_safe_fromstring_blocks_general_entity_file_read():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as secret_file:
        secret_file.write("SECRET")
        secret_file.flush()
        path = Path(secret_file.name).as_posix()
        payload = (
            '<?xml version="1.0"?>'
            f'<!DOCTYPE root [<!ENTITY xxe SYSTEM "file://{path}">]>'
            '<root>&xxe;</root>'
        ).encode()
        root = safe_fromstring(payload)
        assert root.text is None


def test_safe_fromstring_blocks_parameter_entity_file_probe():
    # read a local file's contents and splice them into the DTD so they can
    # later be referenced as a general entity.
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt') as secret_file:
        secret_file.write('<!ENTITY leaked "SECRET">')
        secret_file.flush()
        path = Path(secret_file.name).as_posix()
        payload = (
            '<?xml version="1.0"?>'
            f'<!DOCTYPE root [<!ENTITY % xxe SYSTEM "file://{path}"> %xxe;]>'
            '<root>&leaked;</root>'
        ).encode()
        root = safe_fromstring(payload)
        assert root.text is None


@pytest.mark.parametrize("forbidden_kwargs", [
    {'resolve_entities': True},
    {'no_network': False},
    {'load_dtd': True},
    {'dtd_validation': True},
])
def test_get_safe_xml_parser_rejects_overridden_security_options(forbidden_kwargs):
    with pytest.raises(TypeError):
        get_safe_xml_parser(**forbidden_kwargs)


def test_get_safe_xml_parser_allows_non_security_options():
    parser = get_safe_xml_parser(remove_comments=True)
    root = etree.fromstring(b'<root><!-- comment --><child/></root>', parser=parser)
    assert len(root) == 1


def test_XML_is_an_alias_of_safe_fromstring():
    # XML is for call sites that embed an XML literal (matching lxml's own
    # etree.XML/etree.fromstring naming convention); it must stay behaviorally
    # identical to safe_fromstring, not just similarly named.
    assert XML is safe_fromstring


def test_safe_fromstring_returns_the_element_it_validated():
    # Regression guard: must return the element it already validated, not
    # silently re-parse with a different, unconfigured parser.
    # remove_comments=True makes an unconfigured re-parse observable.
    xml_string = b'<root><!-- comment --><child/></root>'
    root = safe_fromstring(xml_string, remove_comments=True)
    assert list(root.iter(etree.Comment)) == []
