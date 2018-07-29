from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from dimagi.ext.jsonobject import StringProperty
from casexml.apps.case.models import CommCareCase


class DynamicPropertiesTest(SimpleTestCase):

    def test_normal(self):
        case = CommCareCase(foo='some property', bar='some other property')
        props = case.dynamic_case_properties()
        self.assertEqual(2, len(props))
        self.assertEqual('some property', props['foo'])
        self.assertEqual('some other property', props['bar'])

    def test_subclass(self):
        class CaseWithNewProperty(CommCareCase):
            new_property = StringProperty()

            class Meta(object):
                # For some reason this is necessary for travis
                app_label = "case"

        case = CaseWithNewProperty(new_property='some property', bar='some other property')
        props = case.dynamic_case_properties()
        self.assertEqual(2, len(props))
        self.assertEqual('some property', props['new_property'])
        self.assertEqual('some other property', props['bar'])
