from django.test import SimpleTestCase

from corehq.apps.reports.tasks import find_question_id


class FindQuestionIdTests(SimpleTestCase):
    def test_returns_none_when_not_found(self):
        form = {}

        result = find_question_id(form, 'my_attachment')
        self.assertIsNone(result)

    def test_finds_attachment_in_property(self):
        form = {'attachment': 'my_attachment'}

        result = find_question_id(form, 'my_attachment')
        self.assertEqual(result, ['attachment'])

    def test_finds_property_in_nested_form(self):
        nested_form = {'attachment': 'my_attachment'}
        form = {'nested': nested_form}

        result = find_question_id(form, 'my_attachment')
        self.assertEqual(result, ['nested', 'attachment'])

    def test_finds_property_in_list(self):
        nested_form = {'attachment': 'my_attachment'}
        form = {'nested_list': [nested_form]}

        result = find_question_id(form, 'my_attachment')
        self.assertEqual(result, ['nested_list', 'attachment'])

    def test_handles_invalid_list_item(self):
        form = {'bad_list': ['']}

        result = find_question_id(form, 'my_attachment')
        self.assertIsNone(result)
