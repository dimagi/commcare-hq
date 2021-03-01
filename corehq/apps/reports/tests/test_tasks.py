from django.test import SimpleTestCase

from corehq.apps.reports.tasks import _get_question_id_for_attachment, _find_path_to_question_id


class GetQuestionIdTests(SimpleTestCase):
    def test_returns_question_id_when_found(self):
        form = {'attachment': 'my_attachment'}

        result = _get_question_id_for_attachment(form, 'my_attachment')
        self.assertEqual(result, 'attachment')

    def test_returns_nested_question_id_when_found(self):
        nested_form = {'attachment': 'my_attachment'}
        form = {'nested': nested_form}

        result = _get_question_id_for_attachment(form, 'my_attachment')
        self.assertEqual(result, 'nested-attachment')

    def test_returns_none_when_not_found(self):
        form = {}

        result = _get_question_id_for_attachment(form, 'my_attachment')
        self.assertIsNone(result)


class FindPathToQuestionIdTests(SimpleTestCase):
    def test_returns_none_when_not_found(self):
        form = {}

        result = _find_path_to_question_id(form, 'my_attachment')
        self.assertIsNone(result)

    def test_finds_attachment_in_property(self):
        form = {'attachment': 'my_attachment'}

        result = _find_path_to_question_id(form, 'my_attachment')
        self.assertEqual(result, ['attachment'])

    def test_finds_property_in_nested_form(self):
        nested_form = {'attachment': 'my_attachment'}
        form = {'nested': nested_form}

        result = _find_path_to_question_id(form, 'my_attachment')
        self.assertEqual(result, ['nested', 'attachment'])

    def test_finds_property_in_list(self):
        nested_form = {'attachment': 'my_attachment'}
        form = {'nested_list': [nested_form]}

        result = _find_path_to_question_id(form, 'my_attachment')
        self.assertEqual(result, ['nested_list', 'attachment'])

    def test_handles_invalid_list_item(self):
        form = {'bad_list': ['']}

        result = _find_path_to_question_id(form, 'my_attachment')
        self.assertIsNone(result)

    def test_finds_basename(self):
        form = {'attachment': '/path/to/my/attachment.ext'}

        result = _find_path_to_question_id(form, 'attachment.ext', use_basename=True)
        self.assertEqual(result, ['attachment'])

    def test_does_not_find_basename(self):
        form = {'attachment': '/path/to/my/attachment.ext'}

        result = _find_path_to_question_id(form, 'attachment.ext')
        self.assertIsNone(result)
