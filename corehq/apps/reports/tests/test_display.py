from unittest.mock import patch

from django.test import SimpleTestCase

from corehq.apps.hqcase.utils import SYSTEM_FORM_XMLNS, SYSTEM_FORM_XMLNS_MAP

from corehq.apps.reports.display import xmlns_to_name
from corehq.util.test_utils import generate_cases

UNKNOWN_XMLNS = "http://demo.co/form"
KNOWN_XMLNS = SYSTEM_FORM_XMLNS
KNOWN_XMLNS_DISPLAY = SYSTEM_FORM_XMLNS_MAP[KNOWN_XMLNS]


@patch("corehq.apps.reports.display.get_form_analytics_metadata", new=lambda *a, **k: None)
class TestXmlnsToName(SimpleTestCase):
    @generate_cases([
        (UNKNOWN_XMLNS, UNKNOWN_XMLNS),
        (f"{UNKNOWN_XMLNS} > form name", UNKNOWN_XMLNS, "form name"),
        (f"{UNKNOWN_XMLNS} ] form name", UNKNOWN_XMLNS, "form name", " ] "),
        (KNOWN_XMLNS_DISPLAY, KNOWN_XMLNS),
        (f"{KNOWN_XMLNS_DISPLAY} > form name", KNOWN_XMLNS, "form name"),
        (f"{KNOWN_XMLNS_DISPLAY} ] form name", KNOWN_XMLNS, "form name", " ] "),
    ])
    def test_xmlns_to_name(self, expected, xmlns, form_name=None, separator=None):
        name = xmlns_to_name("domain", xmlns, "123", separator=separator, form_name=form_name)
        self.assertEqual(name, expected)
