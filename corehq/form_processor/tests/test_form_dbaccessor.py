from io import BytesIO

from django.core.files.uploadedfile import UploadedFile
from django.test import TestCase

from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import XFormInstance
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded
from corehq.form_processor.utils.xform import FormSubmissionBuilder

DOMAIN = 'test-form-accessor'


@sharded
class FormSubmissionBuilderTests(TestCase, TestXmlMixin):

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms(DOMAIN)
        super().tearDown()

    def test_update_responses(self):
        formxml = FormSubmissionBuilder(
            form_id='123',
            form_properties={
                'breakfast': 'toast',   # Simple questions
                'lunch': 'sandwich',
                'cell': {               # Simple group
                    'cytoplasm': 'squishy',
                    'organelles': 'grainy',
                },
                'shelves': [            # Simple repeat group
                    {'position': 'top'},
                    {'position': 'middle'},
                    {'position': 'bottom'},
                ],
                'grandparent': [        # Repeat group with child group
                    {'name': 'Haruki'},
                    {'name': 'Sugako'},
                    {
                        'name': 'Emma',
                        'parent': {
                            'name': 'Haruki',
                            'child': {
                                'name': 'Nao',
                            },
                        }
                    },
                ],
                'body': [               # Repeat group with child repeat group
                    {'arm': [
                        {'elbow': '1'},
                        {'finger': '5'},
                    ]},
                    {'leg': [
                        {'knee': '1'},
                        {'toe': '5'},
                    ]},
                ],
            }
        ).as_xml_string()
        pic = UploadedFile(BytesIO(b"fake"), 'pic.jpg', content_type='image/jpeg')
        xform = submit_form_locally(formxml, DOMAIN, attachments={"image": pic}).xform

        updates = {
            'breakfast': 'fruit',
            'cell/organelles': 'bulbous',
            'shelves[1]/position': 'third',
            'shelves[3]/position': 'first',
            'grandparent[1]/name': 'Haruki #1',
            'grandparent[3]/name': 'Ema',
            'grandparent[3]/parent/name': 'Haruki #2',
            'grandparent[3]/parent/child/name': 'Nao-chan',
            'body[1]/arm[1]/elbow': '2',
            'body[2]/leg[2]/toe': '10',
        }
        errors = FormProcessorInterface(DOMAIN).update_responses(xform, updates, 'user1')
        form = XFormInstance.objects.get_form(xform.form_id)
        self.assertEqual(0, len(errors))
        self.assertEqual('fruit', form.form_data['breakfast'])
        self.assertEqual('sandwich', form.form_data['lunch'])
        self.assertEqual('squishy', form.form_data['cell']['cytoplasm'])
        self.assertEqual('bulbous', form.form_data['cell']['organelles'])
        self.assertEqual('third', form.form_data['shelves'][0]['position'])
        self.assertEqual('middle', form.form_data['shelves'][1]['position'])
        self.assertEqual('first', form.form_data['shelves'][2]['position'])
        self.assertEqual('Haruki #1', form.form_data['grandparent'][0]['name'])
        self.assertEqual('Sugako', form.form_data['grandparent'][1]['name'])
        self.assertEqual('Ema', form.form_data['grandparent'][2]['name'])
        self.assertEqual('Haruki #2', form.form_data['grandparent'][2]['parent']['name'])
        self.assertEqual('Nao-chan', form.form_data['grandparent'][2]['parent']['child']['name'])
        self.assertEqual('2', form.form_data['body'][0]['arm'][0]['elbow'])
        self.assertEqual('5', form.form_data['body'][0]['arm'][1]['finger'])
        self.assertEqual('1', form.form_data['body'][1]['leg'][0]['knee'])
        self.assertEqual('10', form.form_data['body'][1]['leg'][1]['toe'])
        self.assertIn("image", form.attachments)
        self.assertEqual(form.get_attachment("image"), b"fake")

    def test_update_responses_error(self):
        formxml = FormSubmissionBuilder(form_id='123', form_properties={'nine': 'nueve'}).as_xml_string()
        xform = submit_form_locally(formxml, DOMAIN).xform

        updates = {'eight': 'ocho'}
        errors = FormProcessorInterface(DOMAIN).update_responses(xform, updates, 'user1')
        self.assertEqual(['eight'], errors)

    def test_update_responses_preserves_build_id(self):
        formxml = FormSubmissionBuilder(form_id='123', form_properties={'nine': 'nueve'}).as_xml_string()
        xform = submit_form_locally(formxml, DOMAIN).xform
        xform.build_id = 'b1234'
        xform.save()

        updates = {'eight': 'ocho'}
        FormProcessorInterface(DOMAIN).update_responses(xform, updates, 'user1')

        new_xform = XFormInstance.objects.partitioned_get(xform.form_id)
        old_xform = XFormInstance.objects.partitioned_get(new_xform.deprecated_form_id)
        self.assertEqual(old_xform.build_id, 'b1234')
        self.assertEqual(new_xform.build_id, 'b1234')
