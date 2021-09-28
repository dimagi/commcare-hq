from django.test import SimpleTestCase

from corehq.apps.reports.tasks import _get_question_id_for_attachment


class GetQuestionIdTests(SimpleTestCase):

    def test_returns_question_id_when_found(self):
        form = {'attachment': 'my_attachment'}

        result = _get_question_id_for_attachment(form, 'my_attachment')
        self.assertEqual(result, 'attachment')

    def test_returns_question_id_when_found_in_nested_form(self):
        nested_form = {'attachment': 'my_attachment'}
        form = {'nested': nested_form}

        result = _get_question_id_for_attachment(form, 'my_attachment')
        self.assertEqual(result, 'nested-attachment')

    def test_returns_question_id_when_found_in_list(self):
        nested_form = {'attachment': 'my_attachment'}
        form = {'nested_list': [nested_form]}

        result = _get_question_id_for_attachment(form, 'my_attachment')
        self.assertEqual(result, 'nested_list-attachment')

    def test_handles_invalid_list_item(self):
        form = {'bad_list': ['']}

        result = _get_question_id_for_attachment(form, 'my_attachment')
        self.assertIsNone(result)

    def test_returns_none_when_not_found(self):
        form = {}

        result = _get_question_id_for_attachment(form, 'my_attachment')
        self.assertIsNone(result)

    def test_returns_question_id_when_found_as_abs_path_basename(self):
        form = {'attachment': '/path/to/my/attachment.ext'}

        result = _get_question_id_for_attachment(form, 'attachment.ext')
        self.assertEqual(result, 'attachment')

    def test_returns_none_when_found_as_rel_path_basename(self):
        """
        The original bug this aims to solve only occurs for absolute paths
        To minimize impact of the change, only look at basenames of absolute paths
        """
        form = {'attachment': 'path/to/my/attachment.ext'}

        result = _get_question_id_for_attachment(form, 'attachment.ext')
        self.assertIsNone(result)
