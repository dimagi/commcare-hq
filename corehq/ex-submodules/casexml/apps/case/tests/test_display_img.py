import base64
import os

from django.test import TestCase

from corehq.apps.hqcase.case_helper import CaseHelper
from corehq.form_processor.models import CommCareCase

DOMAIN = 'test-domain'


def get_case_display_img():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    png_filename = os.sep.join((base_dir, 'data', 'case_display_img.png'))
    with open(png_filename, 'rb') as png_file:
        return png_file.read()


def to_base64_str(binary):
    base64_ascii = base64.b64encode(binary)
    return base64_ascii.decode('ascii')


def to_binary(base64_str):
    base64_ascii = base64_str.encode('ascii')
    return base64.b64decode(base64_ascii)


class TestDisplayImg(TestCase):
    """
    Tests saving and retrieving a base64-encoded case display image as a
    case property value.
    """

    def test_display_img(self):
        img_binary = get_case_display_img()
        self.assertEqual(len(img_binary), 3701)  # 3.7KB PNG image

        helper = CaseHelper(domain=DOMAIN)
        helper.create_case({
            'case_type': 'person',
            'case_name': 'Obama',
            'properties': {
                'case_display_img': to_base64_str(img_binary),
            }
        })
        case_id = helper.case.case_id

        case = CommCareCase.objects.get_case(domain=DOMAIN, case_id=case_id)
        img_str = case.get_case_property('case_display_img')
        self.assertEqual(to_binary(img_str), img_binary)
