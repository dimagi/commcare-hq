from django.contrib.messages.storage.fallback import FallbackStorage
from django.db import IntegrityError, transaction
from django.http import Http404
from django.test import RequestFactory, TestCase
from django.urls import reverse

from corehq.apps.document_templates.models import Area, Template
from corehq.apps.document_templates.views import (
    DeleteDocumentTemplateView,
    EditDocumentTemplateView,
    NewDocumentTemplateView,
    get_area_names,
)

DOMAIN = 'document-templates-test'
OTHER_DOMAIN = 'document-templates-other'


def _post(view_class, pk=None, data=None, domain=DOMAIN):
    request = RequestFactory().post('/', data or {})
    request.session = {}
    request._messages = FallbackStorage(request)
    kwargs = {'domain': domain, **({'pk': pk} if pk else {})}
    view = view_class()
    view.setup(request, **kwargs)
    return view.post(request, **kwargs)


class TestNewDocumentTemplateView(TestCase):

    def test_creates_a_template_in_the_domain_and_redirects_to_the_list(self):
        response = _post(NewDocumentTemplateView, data={'name': 'Welcome', 'slug': 'welcome', 'area_body': 'Hi'})
        assert response.status_code == 302
        assert response.url == reverse('document_templates', args=[DOMAIN])
        template = Template.objects.get(domain=DOMAIN, slug='welcome')
        assert template.name == 'Welcome'


class TestDeleteDocumentTemplateView(TestCase):

    def test_marks_the_template_deleted_and_redirects_to_the_list(self):
        template = Template.objects.create(domain=DOMAIN, name='Welcome', slug='welcome', areas={})
        response = _post(DeleteDocumentTemplateView, template.pk)
        assert response.status_code == 302
        assert response.url == reverse('document_templates', args=[DOMAIN])
        template.refresh_from_db()
        assert template.deleted

    def test_deleted_template_cannot_be_deleted_again(self):
        template = Template.objects.create(
            domain=DOMAIN, name='Gone', slug='gone', areas={}, deleted=True,
        )
        with self.assertRaises(Http404):
            _post(DeleteDocumentTemplateView, template.pk)

    def test_slug_of_a_deleted_template_can_be_reused(self):
        Template.objects.create(domain=DOMAIN, name='Old', slug='welcome', areas={}, deleted=True)
        Template.objects.create(domain=DOMAIN, name='New', slug='welcome', areas={})

    def test_active_slug_is_still_unique(self):
        Template.objects.create(domain=DOMAIN, name='A', slug='welcome', areas={})
        with self.assertRaises(IntegrityError), transaction.atomic():
            Template.objects.create(domain=DOMAIN, name='B', slug='welcome', areas={})

    def test_keeps_other_templates(self):
        template = Template.objects.create(domain=DOMAIN, name='Welcome', slug='welcome', areas={})
        other = Template.objects.create(domain=DOMAIN, name='Other', slug='other', areas={})
        _post(DeleteDocumentTemplateView, template.pk)
        assert list(Template.objects.filter(deleted=False)) == [other]

    def test_cannot_delete_a_template_of_another_domain(self):
        template = Template.objects.create(domain=OTHER_DOMAIN, name='Theirs', slug='theirs', areas={})
        with self.assertRaises(Http404):
            _post(DeleteDocumentTemplateView, template.pk)
        assert Template.objects.filter(pk=template.pk).exists()


class TestEditDocumentTemplateView(TestCase):

    def _data(self, **overrides):
        data = {'name': 'Renamed', 'slug': 'renamed', 'area_body': 'New **body**'}
        return {**data, **overrides}

    def test_updates_name_slug_and_areas(self):
        template = Template.objects.create(
            domain=DOMAIN, name='Welcome', slug='welcome',
            areas={'body': Area(value='Old')},
        )
        response = _post(EditDocumentTemplateView, template.pk, self._data())
        assert response.status_code == 302
        template.refresh_from_db()
        assert (template.name, template.slug) == ('Renamed', 'renamed')
        assert template.areas['body'] == Area(value='New **body**')

    def test_can_save_without_changing_the_slug(self):
        template = Template.objects.create(domain=DOMAIN, name='Welcome', slug='welcome', areas={})
        response = _post(EditDocumentTemplateView, template.pk, self._data(slug='welcome'))
        assert response.status_code == 302
        template.refresh_from_db()
        assert template.name == 'Renamed'

    def test_areas_are_rewritten_from_the_current_template_areas(self):
        template = Template.objects.create(
            domain=DOMAIN, name='Welcome', slug='welcome',
            areas={'removed': Area(value='Gone')},
        )
        _post(EditDocumentTemplateView, template.pk, self._data())
        template.refresh_from_db()
        # jsonb does not keep key order
        assert set(template.areas) == set(get_area_names())
        assert template.areas['header'].value == ''

    def test_cannot_edit_a_template_of_another_domain(self):
        template = Template.objects.create(domain=OTHER_DOMAIN, name='Theirs', slug='theirs', areas={})
        with self.assertRaises(Http404):
            _post(EditDocumentTemplateView, template.pk, self._data())
        template.refresh_from_db()
        assert template.name == 'Theirs'
