import inspect
import uuid
from io import BytesIO

from couchdbkit import ResourceNotFound
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from PIL import Image

from corehq.apps.document_templates.images import save_image
from corehq.apps.document_templates.views import (
    preview_document,
    preview_document_variables,
)
from corehq.apps.hqmedia.models import CommCareImage

DOMAIN = 'document-templates-preview-test'

VALUES = {'area_header': '', 'area_address': '', 'area_body': 'Dear {{ name }}', 'area_footer': ''}


def _post(view, data):
    return inspect.unwrap(view)(RequestFactory().post('/', data), DOMAIN)


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
    assert response['Content-Disposition'] == 'inline; filename="preview.pdf"'
    assert response['X-Content-Type-Options'] == 'nosniff'
    assert response.getvalue().startswith(b'%PDF')


def test_preview_view_leaves_unfilled_variables_empty():
    response = _post(preview_document, VALUES)
    assert response.status_code == 200
    assert response.getvalue().startswith(b'%PDF')


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


def _png():
    buffer = BytesIO()
    Image.new('RGB', (10, 20), color=tuple(uuid.uuid4().bytes[:3])).save(buffer, format='PNG')
    return buffer.getvalue()


def _delete_image(image_id):
    try:
        CommCareImage.get(image_id).delete()
    except ResourceNotFound:
        pass


def test_variables_view_ignores_the_markdown_of_an_image_area():
    values = {**VALUES, 'area_body_type': 'image', 'area_body': 'Dear {{ name }}', 'area_header': '{{ street }}'}
    content = _post(preview_document_variables, values).content.decode()
    assert 'name="context_street"' in content
    assert 'context_name' not in content


def test_variables_view_treats_an_unknown_type_as_markdown():
    content = _post(preview_document_variables, {**VALUES, 'area_body_type': 'video'}).content.decode()
    assert 'name="context_name"' in content


class TestPreviewWithImages(TestCase):

    def _image_id(self, domain=DOMAIN):
        image_id = save_image(domain, SimpleUploadedFile('logo.png', _png()), 'user')
        self.addCleanup(_delete_image, image_id)
        return image_id

    def test_image_area_is_drawn(self):
        values = {**VALUES, 'area_header_type': 'image', 'area_header_image': self._image_id()}
        response = _post(preview_document, values)
        assert response.status_code == 200
        assert b'/Subtype /Image' in response.getvalue()

    def test_markdown_of_an_image_area_is_not_rendered(self):
        values = {
            **VALUES,
            'area_header_type': 'image',
            'area_header': '{% if %}',  # a syntax error that would be reported for markdown
            'area_header_image': self._image_id(),
        }
        assert _post(preview_document, values).status_code == 200

    def test_image_area_without_an_image_is_blank(self):
        response = _post(preview_document, {**VALUES, 'area_header_type': 'image'})
        assert response.status_code == 200
        assert b'/Subtype /Image' not in response.getvalue()

    def test_image_of_another_project_is_reported(self):
        values = {**VALUES, 'area_header_type': 'image', 'area_header_image': self._image_id('other-domain')}
        response = _post(preview_document, values)
        assert response.status_code == 400
        assert 'header: The image does not belong to this project.' in response.content.decode()

    def test_image_that_does_not_exist_is_reported(self):
        values = {**VALUES, 'area_footer_type': 'image', 'area_footer_image': 'missing'}
        response = _post(preview_document, values)
        assert response.status_code == 400
        assert 'footer: The image does not exist.' in response.content.decode()
