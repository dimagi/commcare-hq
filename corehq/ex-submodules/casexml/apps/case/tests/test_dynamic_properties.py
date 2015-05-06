from django.test import SimpleTestCase
from dimagi.ext.jsonobject import StringProperty
from casexml.apps.case.models import CommCareCase


class DynamicPropertiesTest(SimpleTestCase):

    def test_normal(self):
        case = CommCareCase(foo='some property', bar='some other property')
        props = case.dynamic_case_properties()
        self.assertEqual(2, len(props))
        props_dict = dict(props)
        self.assertEqual('some property', props_dict['foo'])
        self.assertEqual('some other property', props_dict['bar'])

    def test_subclass(self):
        class CaseWithNewProperty(CommCareCase):
            new_property = StringProperty()

            class Meta:
                # For some reason this is necessary for travis
                app_label = "case"

        case = CaseWithNewProperty(new_property='some property', bar='some other property')
        props = case.dynamic_case_properties()
        self.assertEqual(2, len(props))
        props_dict = dict(props)
        self.assertEqual('some property', props_dict['new_property'])
        self.assertEqual('some other property', props_dict['bar'])
