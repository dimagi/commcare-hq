import inspect

from django.test import RequestFactory

from corehq.apps.document_templates.views import (
    preview_document,
    preview_document_variables,
)

VALUES = {'area_header': '', 'area_address': '', 'area_body': 'Dear {{ name }}', 'area_footer': ''}


def _post(view, data):
    return inspect.unwrap(view)(RequestFactory().post('/', data), 'test-domain')


def test_variables_view_has_an_input_for_each_variable():
    values = {**VALUES, 'area_address': '{{ street }}', 'area_body': 'Dear {{ name }} {{ name }}'}
    content = _post(preview_document_variables, values).content.decode()
    assert 'name="context_street"' in content
    assert content.count('name="context_name"') == 1


def test_variables_view_keeps_values_already_entered():
    values = {**VALUES, 'context_name': 'Ada "Lovelace"', 'context_removed': 'x'}
    content = _post(preview_document_variables, values).content.decode()
    assert 'value="Ada &quot;Lovelace&quot;"' in content
    assert 'context_removed' not in content


def test_variables_view_without_variables_has_no_inputs():
    content = _post(preview_document_variables, {**VALUES, 'area_body': 'Hello'}).content.decode()
    assert '<input' not in content
    assert 'does not use any variables' in content


def test_variables_view_shows_a_template_error():
    response = _post(preview_document_variables, {**VALUES, 'area_body': '{% if %}'})
    content = response.content.decode()
    assert 'alert-danger' in content
    assert '<input' not in content


def test_preview_view_renders_a_pdf():
    response = _post(preview_document, {**VALUES, 'context_name': 'Ada'})
    assert response.status_code == 200
    assert response['Content-Type'] == 'application/pdf'
    assert response.content.startswith(b'%PDF')


def test_preview_view_leaves_unfilled_variables_empty():
    response = _post(preview_document, VALUES)
    assert response.status_code == 200
    assert response.content.startswith(b'%PDF')


def test_preview_view_ignores_context_for_unused_variables():
    response = _post(preview_document, {**VALUES, 'context_name': 'Ada', 'context_other': 'x'})
    assert response.status_code == 200


def test_preview_view_reports_a_template_error():
    response = _post(preview_document, {**VALUES, 'area_body': '{% if %}'})
    assert response.status_code == 400
    assert 'syntax error in body' in response.content.decode()


def test_preview_view_escapes_errors():
    response = _post(preview_document, {**VALUES, 'area_body': '{% if <script> %}'})
    assert response.status_code == 400
    assert '<script>' not in response.content.decode()
