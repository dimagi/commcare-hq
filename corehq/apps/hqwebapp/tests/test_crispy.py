from unittest.mock import MagicMock, patch

from django import forms
from django.test import SimpleTestCase

from corehq.apps.hqwebapp.crispy import FieldsetAccordionGroup
from corehq.apps.hqwebapp.utils.bootstrap import (
    BOOTSTRAP_3,
    BOOTSTRAP_5,
    clear_bootstrap_version,
    get_bootstrap_version,
    set_bootstrap_version3,
    set_bootstrap_version5,
)


class TestFieldsetAccordionGroup(SimpleTestCase):
    """Test that FieldsetAccordionGroup correctly injects use_bootstrap5 into render context"""

    def setUp(self):
        # Create a simple form for testing
        class TestForm(forms.Form):
            test_field = forms.CharField()

        self.form = TestForm()
        self.accordion = FieldsetAccordionGroup(
            "Test Accordion",
            "test_field"
        )

    def tearDown(self):
        # Clean up thread-local bootstrap version after each test
        clear_bootstrap_version()

    @patch('corehq.apps.hqwebapp.crispy.render_to_string')
    @patch.object(FieldsetAccordionGroup, 'get_rendered_fields')
    def test_accordion_injects_use_bootstrap5_false_when_bootstrap3(self, mock_get_fields, mock_render):
        """When Bootstrap 3 is set, use_bootstrap5 should be False in the render context"""
        set_bootstrap_version3()
        self.assertEqual(get_bootstrap_version(), BOOTSTRAP_3)

        mock_get_fields.return_value = "<div>field</div>"
        mock_render.return_value = "<div>rendered</div>"

        context = MagicMock()
        result = self.accordion.render(self.form, context)

        mock_render.assert_called_once()
        call_args = mock_render.call_args
        template_context = call_args[0][1]
        self.assertIn('use_bootstrap5', template_context)
        self.assertFalse(template_context['use_bootstrap5'])
        self.assertEqual(result, "<div>rendered</div>")

    @patch('corehq.apps.hqwebapp.crispy.render_to_string')
    @patch.object(FieldsetAccordionGroup, 'get_rendered_fields')
    def test_accordion_injects_use_bootstrap5_true_when_bootstrap5(self, mock_get_fields, mock_render):
        """When Bootstrap 5 is set, use_bootstrap5 should be True in the render context"""
        set_bootstrap_version5()
        self.assertEqual(get_bootstrap_version(), BOOTSTRAP_5)

        mock_get_fields.return_value = "<div>field</div>"
        mock_render.return_value = "<div>rendered</div>"

        context = MagicMock()
        result = self.accordion.render(self.form, context)

        mock_render.assert_called_once()
        call_args = mock_render.call_args
        template_context = call_args[0][1]
        self.assertIn('use_bootstrap5', template_context)
        self.assertTrue(template_context['use_bootstrap5'])
        self.assertEqual(result, "<div>rendered</div>")

    @patch('corehq.apps.hqwebapp.crispy.render_to_string')
    @patch.object(FieldsetAccordionGroup, 'get_rendered_fields')
    def test_accordion_defaults_to_bootstrap3_when_not_set(self, mock_get_fields, mock_render):
        """When no bootstrap version is set, it should default to Bootstrap 3"""
        clear_bootstrap_version()
        self.assertEqual(get_bootstrap_version(), BOOTSTRAP_3)

        mock_get_fields.return_value = "<div>field</div>"
        mock_render.return_value = "<div>rendered</div>"

        context = MagicMock()
        result = self.accordion.render(self.form, context)

        mock_render.assert_called_once()
        call_args = mock_render.call_args
        template_context = call_args[0][1]
        self.assertIn('use_bootstrap5', template_context)
        self.assertFalse(template_context['use_bootstrap5'])
        self.assertEqual(result, "<div>rendered</div>")
