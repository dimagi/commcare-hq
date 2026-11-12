"""Tests for checkbox widget rendering, in particular that field validation
errors are visible on Bootstrap 5 forms (SAAS-19669).

Bootstrap 5 keeps ``.invalid-feedback`` at ``display: none`` unless a
preceding sibling has the ``is-invalid`` class, so the widget must preserve
the ``is-invalid`` class that crispy forms adds when a field has errors, and
its wrapper div (the error span's actual sibling) must carry it too.
"""
import re

from django import forms
from django.template import Context, Template

import crispy_forms.bootstrap as twbscrispy
import crispy_forms.layout as crispy
import pytest
from crispy_forms.helper import FormHelper
from unmagic import fixture, use  # https://github.com/dimagi/pytest-unmagic

from corehq.apps.hqwebapp.utils.bootstrap import (
    clear_bootstrap_version,
    set_bootstrap_version3,
    set_bootstrap_version5,
)
from corehq.apps.hqwebapp.widgets import (
    BootstrapCheckboxInput,
    BootstrapSwitchInput,
)


@fixture
def bootstrap5():
    set_bootstrap_version5()
    try:
        yield
    finally:
        clear_bootstrap_version()


@fixture
def bootstrap3():
    set_bootstrap_version3()
    try:
        yield
    finally:
        clear_bootstrap_version()


def _rendered_input_classes(widget, incoming_class):
    context = widget.get_context('is_active', True, {'class': incoming_class})
    match = re.search(r'class="([^"]*)"', context['attrs'])
    return match.group(1)


@use(bootstrap5)
@pytest.mark.parametrize('incoming_class, expected', [
    # crispy's bootstrap5 checkbox path: is-invalid on error, plus the
    # lowercased widget class name that CrispyFieldNode always appends
    ('form-check-input is-invalid bootstrapcheckboxinput', 'form-check-input is-invalid'),
    # crispy's PrependedText path styles checkboxes as generic controls
    ('form-control is-invalid', 'form-check-input is-invalid'),
    ('form-select is-invalid', 'form-check-input is-invalid'),
    ('form-check-input bootstrapcheckboxinput', 'form-check-input'),
    ('', 'form-check-input'),
])
def test_checkbox_input_classes_bootstrap5(incoming_class, expected):
    assert _rendered_input_classes(BootstrapCheckboxInput(), incoming_class) == expected


@use(bootstrap5)
def test_custom_widget_classes_are_preserved():
    classes = _rendered_input_classes(BootstrapCheckboxInput(), 'custom-class is-invalid')
    assert classes == 'form-check-input custom-class is-invalid'


@use(bootstrap5)
def test_switch_input_filters_its_own_class_name():
    classes = _rendered_input_classes(BootstrapSwitchInput(), 'form-control is-invalid bootstrapswitchinput')
    assert classes == 'form-check-input is-invalid'


@use(bootstrap5)
@pytest.mark.parametrize('incoming_class, is_invalid', [
    ('form-check-input is-invalid', True),
    ('form-check-input', False),
])
def test_context_exposes_is_invalid(incoming_class, is_invalid):
    context = BootstrapCheckboxInput().get_context('is_active', True, {'class': incoming_class})
    assert context['is_invalid'] is is_invalid


@use(bootstrap5)
def test_switch_wrapper_gets_is_invalid():
    html = BootstrapSwitchInput().render('is_active', True, attrs={'class': 'is-invalid'})
    assert '<div class="form-check form-switch is-invalid">' in html


@use(bootstrap3)
def test_checkbox_input_classes_bootstrap3():
    classes = _rendered_input_classes(BootstrapCheckboxInput(), 'form-control is-invalid')
    assert classes == 'bootstrapcheckboxinput is-invalid'


class DemoForm(forms.Form):
    is_active = forms.BooleanField(
        label="Active Status",
        required=False,
        widget=BootstrapCheckboxInput(inline_label="Single Sign On is active"),
    )

    def __init__(self, *args, use_prepended_text=False, error=False, **kwargs):
        super().__init__(*args, **kwargs)
        self._error = error
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            twbscrispy.PrependedText('is_active', '') if use_prepended_text
            else crispy.Field('is_active')
        )

    def clean_is_active(self):
        if self._error:
            raise forms.ValidationError("checkbox error")
        return self.cleaned_data['is_active']


def _render_crispy_bootstrap5(form):
    template = Template("{% load crispy_forms_tags %}{% crispy form %}")
    return template.render(Context({'form': form, 'use_bootstrap5': True}))


def _get_input_tag(html):
    return re.search(r'<input[^>]*name="is_active"[^>]*>', html).group(0)


@use(bootstrap5)
@pytest.mark.parametrize('use_prepended_text', [False, True])
def test_validation_error_is_visible_on_bootstrap5_form(use_prepended_text):
    form = DemoForm(data={'is_active': 'on'}, error=True, use_prepended_text=use_prepended_text)
    assert not form.is_valid()
    html = _render_crispy_bootstrap5(form)
    input_tag = _get_input_tag(html)
    assert 'is-invalid' in input_tag
    assert 'form-control' not in input_tag
    # the widget's wrapper div is the invalid-feedback span's preceding
    # sibling, so it needs is-invalid for the span to be displayed
    assert '<div class="form-check is-invalid">' in html
    assert 'invalid-feedback' in html


@use(bootstrap5)
@pytest.mark.parametrize('use_prepended_text', [False, True])
def test_valid_bootstrap5_form_has_no_error_styling(use_prepended_text):
    form = DemoForm(data={'is_active': 'on'}, use_prepended_text=use_prepended_text)
    assert form.is_valid()
    html = _render_crispy_bootstrap5(form)
    assert 'is-invalid' not in html
