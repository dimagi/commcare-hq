from django.test import SimpleTestCase

from ..models import FormAction, OpenCaseAction, UpdateCaseAction


class FormActionTests(SimpleTestCase):

    def test_get_action_properties_for_name_update(self):
        action = OpenCaseAction({'name_update': {'question_path': '/data/name'}})
        properties = list(FormAction.get_action_properties(action))

        assert properties == [('name', '/data/name')]

    def test_get_action_properties_for_update(self):
        action = UpdateCaseAction({'update': {'one': {'question_path': 'q1'}}})
        properties = list(FormAction.get_action_properties(action))

        assert properties == [('one', 'q1')]
