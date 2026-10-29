from django.contrib.messages.storage.fallback import FallbackStorage
from django.db import IntegrityError, transaction
from django.http import Http404
from django.test import RequestFactory, TestCase
from django.urls import reverse

from corehq.apps.document_templates.models import Template
from corehq.apps.document_templates.rendering import get_variable_names
from corehq.apps.document_templates.views import (
    DeleteDocumentTemplateView,
    EditDocumentTemplateView,
)

DOMAIN = 'document-templates-test'
OTHER_DOMAIN = 'document-templates-other'


def _post(view_class, template_id, data=None, domain=DOMAIN):
    request = RequestFactory().post('/', data or {})
    request.session = {}
    request._messages = FallbackStorage(request)
    view = view_class()
    view.setup(request, domain=domain, template_id=template_id)
    return view.post(request, domain=domain, template_id=template_id)


class TestDeleteDocumentTemplateView(TestCase):

    def test_marks_the_template_deleted_and_redirects_to_the_list(self):
        template = Template.objects.create(domain=DOMAIN, name='Welcome', slug='welcome', variables={})
        response = _post(DeleteDocumentTemplateView, template.pk)
        assert response.status_code == 302
        assert response.url == reverse('document_templates', args=[DOMAIN])
        template.refresh_from_db()
        assert template.deleted

    def test_deleted_template_cannot_be_deleted_again(self):
        template = Template.objects.create(
            domain=DOMAIN, name='Gone', slug='gone', variables={}, deleted=True,
        )
        with self.assertRaises(Http404):
            _post(DeleteDocumentTemplateView, template.pk)

    def test_slug_of_a_deleted_template_can_be_reused(self):
        Template.objects.create(domain=DOMAIN, name='Old', slug='welcome', variables={}, deleted=True)
        Template.objects.create(domain=DOMAIN, name='New', slug='welcome', variables={})

    def test_active_slug_is_still_unique(self):
        Template.objects.create(domain=DOMAIN, name='A', slug='welcome', variables={})
        with self.assertRaises(IntegrityError), transaction.atomic():
            Template.objects.create(domain=DOMAIN, name='B', slug='welcome', variables={})

    def test_keeps_other_templates(self):
        template = Template.objects.create(domain=DOMAIN, name='Welcome', slug='welcome', variables={})
        other = Template.objects.create(domain=DOMAIN, name='Other', slug='other', variables={})
        _post(DeleteDocumentTemplateView, template.pk)
        assert list(Template.objects.filter(deleted=False)) == [other]

    def test_cannot_delete_a_template_of_another_domain(self):
        template = Template.objects.create(domain=OTHER_DOMAIN, name='Theirs', slug='theirs', variables={})
        with self.assertRaises(Http404):
            _post(DeleteDocumentTemplateView, template.pk)
        assert Template.objects.filter(pk=template.pk).exists()


class TestEditDocumentTemplateView(TestCase):

    def _data(self, **overrides):
        data = {'name': 'Renamed', 'slug': 'renamed', 'var_body': 'New **body**'}
        return {**data, **overrides}

    def test_updates_name_slug_and_variables(self):
        template = Template.objects.create(
            domain=DOMAIN, name='Welcome', slug='welcome',
            variables={'body': {'type': 'markdown', 'value': 'Old'}},
        )
        response = _post(EditDocumentTemplateView, template.pk, self._data())
        assert response.status_code == 302
        template.refresh_from_db()
        assert (template.name, template.slug) == ('Renamed', 'renamed')
        assert template.variables['body'] == {'type': 'markdown', 'value': 'New **body**'}

    def test_can_save_without_changing_the_slug(self):
        template = Template.objects.create(domain=DOMAIN, name='Welcome', slug='welcome', variables={})
        response = _post(EditDocumentTemplateView, template.pk, self._data(slug='welcome'))
        assert response.status_code == 302
        template.refresh_from_db()
        assert template.name == 'Renamed'

    def test_cannot_take_the_slug_of_another_template(self):
        Template.objects.create(domain=DOMAIN, name='Other', slug='taken', variables={})
        template = Template.objects.create(domain=DOMAIN, name='Welcome', slug='welcome', variables={})
        request = RequestFactory().post('/', self._data(slug='taken'))
        view = EditDocumentTemplateView()
        view.setup(request, domain=DOMAIN, template_id=template.pk)
        assert 'slug' in view.form.errors

    def test_variables_are_rewritten_from_the_current_template_variables(self):
        template = Template.objects.create(
            domain=DOMAIN, name='Welcome', slug='welcome',
            variables={'removed': {'type': 'markdown', 'value': 'Gone'}},
        )
        _post(EditDocumentTemplateView, template.pk, self._data())
        template.refresh_from_db()
        # jsonb does not keep key order
        assert set(template.variables) == set(get_variable_names())
        assert template.variables['header']['value'] == ''

    def test_cannot_edit_a_template_of_another_domain(self):
        template = Template.objects.create(domain=OTHER_DOMAIN, name='Theirs', slug='theirs', variables={})
        with self.assertRaises(Http404):
            _post(EditDocumentTemplateView, template.pk, self._data())
        template.refresh_from_db()
        assert template.name == 'Theirs'
