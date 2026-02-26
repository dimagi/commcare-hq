from django.test import SimpleTestCase

from ..models import FormAction, OpenCaseAction, UpdateCaseAction


class FormActionTests(SimpleTestCase):

    def test_get_action_properties_for_name_update(self):
        action = OpenCaseAction({'name_update': {'question_path': '/data/name'}})
        properties = list(FormAction.get_action_properties(action))

        assert properties == [('name', '/data/name')]

    def test_get_action_properties_ignores_name_update_multi(self):
        action = OpenCaseAction({'name_update_multi': [{'question_path': 'name1'}, {'question_path': 'name2'}]})
        properties = list(FormAction.get_action_properties(action))

        assert properties == []

    def test_get_action_properties_for_update(self):
        action = UpdateCaseAction({'update': {'one': {'question_path': 'q1'}}})
        properties = list(FormAction.get_action_properties(action))

        assert properties == [('one', 'q1')]

    def test_get_action_properties_ignores_update_multi(self):
        action = UpdateCaseAction({'update_multi': {'one': [{'question_path': 'q1'}, {'question_path': 'q2'}]}})
        properties = list(FormAction.get_action_properties(action))

        assert properties == []
