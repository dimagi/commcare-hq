import json

from django.test import RequestFactory

from corehq.apps.document_templates.views import (
    PreviewDocumentView,
    PreviewVariablesView,
)

VALUES = {'var_header': '', 'var_address': '', 'var_body': 'Dear {{ name }}', 'var_footer': ''}


def _post(view_class, data):
    return view_class().post(RequestFactory().post('/', data))


def test_variables_view_returns_the_context_as_json():
    response = _post(PreviewVariablesView, VALUES)
    assert response.status_code == 200
    assert '<textarea' in response.content.decode()
    assert '&quot;name&quot;: &quot;&quot;' in response.content.decode()


def test_variables_view_shows_a_template_error():
    response = _post(PreviewVariablesView, {**VALUES, 'var_body': '{% if %}'})
    content = response.content.decode()
    assert 'alert-danger' in content
    assert '<textarea' not in content


def test_preview_view_renders_the_document():
    response = _post(PreviewDocumentView, {**VALUES, 'context': json.dumps({'name': 'Ada'})})
    assert response.status_code == 200
    assert 'Dear Ada' in response.content.decode()
    assert response['Content-Security-Policy'] == 'sandbox'


def test_preview_view_rejects_invalid_json():
    response = _post(PreviewDocumentView, {**VALUES, 'context': '{not json'})
    assert response.status_code == 400


def test_preview_view_rejects_a_context_that_is_not_an_object():
    response = _post(PreviewDocumentView, {**VALUES, 'context': '["a"]'})
    assert response.status_code == 400
    assert 'JSON object' in response.content.decode()


def test_preview_view_reports_a_missing_variable():
    response = _post(PreviewDocumentView, {**VALUES, 'context': '{}'})
    assert response.status_code == 400
    assert 'name' in response.content.decode()


def test_preview_view_escapes_errors():
    response = _post(PreviewDocumentView, {**VALUES, 'context': '<script>'})
    assert response.status_code == 400
    assert '<script>' not in response.content.decode()
