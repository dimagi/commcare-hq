
from collections import OrderedDict

from django.test import SimpleTestCase

from corehq.form_processor.exceptions import XFormQuestionValueNotFound
from corehq.form_processor.utils.xform import build_form_xml_from_property_dict, get_node
from lxml import etree


class FormSubmissionBuilderTest(SimpleTestCase):

    def test_property_dict_to_xml_empty(self):
        self.assertEqual('', build_form_xml_from_property_dict({}))

    def test_property_dict_to_xml_single_item(self):
        self.assertEqual(
            '<my-property>some value</my-property>',
            build_form_xml_from_property_dict({'my-property': 'some value'})
        )

    def test_property_dict_to_xml_multiple_item(self):
        props = OrderedDict()
        props['p1'] = 'v1'
        props['p2'] = 'v2'
        self.assertEqual(
            '<p1>v1</p1><p2>v2</p2>',
            build_form_xml_from_property_dict(props)
        )

    def test_invalid_tag(self):
        with self.assertRaises(ValueError):
            build_form_xml_from_property_dict({'no spaces': 'are allowed'})

    def test_property_dict_to_xml_group(self):
        body = OrderedDict()
        organs = OrderedDict()
        organs['stomach'] = 'one'
        organs['kidneys'] = 'two'
        body['head'] = 'one'
        body['organs'] = organs
        body['feet'] = 'two'
        self.assertEqual(
            '<head>one</head><organs><stomach>one</stomach><kidneys>two</kidneys></organs><feet>two</feet>',
            build_form_xml_from_property_dict(body)
        )

    def test_property_dict_to_xml_repeat_group(self):
        breakfast = OrderedDict()
        breakfast['cup_of_tea'] = [
            OrderedDict([('flavor', 'hibiscus')]),
            OrderedDict([('flavor', 'assam')]),
        ]
        breakfast['toast'] = [
            'wheat',
            'white',
        ]
        breakfast['muffin'] = 'banana'
        self.assertEqual(
            '<cup_of_tea><flavor>hibiscus</flavor></cup_of_tea>'
            '<cup_of_tea><flavor>assam</flavor></cup_of_tea>'
            '<toast>wheat</toast><toast>white</toast>'
            '<muffin>banana</muffin>',
            build_form_xml_from_property_dict(breakfast)
        )

    def test_get_node(self):
        xml = '''
<data>
    <something>elephant</something>
    <twin>
        <name>romulus</name>
    </twin>
    <twin>
        <name>remus</name>
    </twin>
    <has_attribute attr="dirty" />
</data>
        '''
        root = etree.fromstring(xml)
        self.assertEqual('elephant', get_node(root, '/data/something').text)
        self.assertEqual('romulus', get_node(root, '/data/twin[1]/name').text)
        self.assertEqual('remus', get_node(root, '/data/twin[2]/name').text)
        with self.assertRaises(XFormQuestionValueNotFound):
            get_node(root, '/data/has_attribute/@dirty')
