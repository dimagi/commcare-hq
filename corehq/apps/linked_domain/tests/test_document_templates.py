from datetime import datetime

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

import pytest
import pytz

from corehq.apps.document_templates.images import get_image, get_image_data, save_image
from corehq.apps.document_templates.models import Area, AreaType, Template
from corehq.apps.document_templates.tests.utils import delete_image, make_image
from corehq.apps.linked_domain.document_templates import (
    update_linked_document_template,
)
from corehq.apps.linked_domain.exceptions import DomainLinkError
from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.linked_domain.view_helpers import (
    build_document_template_view_model,
    build_pullable_view_models_from_data_models,
    get_upstream_and_downstream_document_templates,
)
from corehq.blobs.models import BlobMeta

UPSTREAM = 'templates-upstream'
DOWNSTREAM = 'templates-downstream'


def _create_template(domain, slug='welcome', **kwargs):
    kwargs.setdefault('areas', {'body': Area(value='Hello')})
    return Template.objects.create(domain=domain, name='Welcome', slug=slug, **kwargs)


class TestUpdateLinkedDocumentTemplate(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_link = DomainLink.link_domains(DOWNSTREAM, UPSTREAM)
        cls.addClassCleanup(cls.domain_link.delete)

    def _update(self, upstream_template):
        update_linked_document_template(self.domain_link, upstream_template.slug)

    def test_first_link_copies_the_template(self):
        upstream = _create_template(UPSTREAM)

        self._update(upstream)

        downstream = Template.objects.get(domain=DOWNSTREAM)
        assert downstream.is_linked
        assert (downstream.name, downstream.slug) == ('Welcome', 'welcome')
        assert downstream.areas == {'body': Area(value='Hello')}

    def test_later_links_update_the_copy(self):
        upstream = _create_template(UPSTREAM)
        self._update(upstream)
        upstream.name = 'Renamed'
        upstream.areas = {'body': Area(value='Changed')}
        upstream.save()

        self._update(upstream)

        downstream = Template.objects.get(domain=DOWNSTREAM)
        assert (downstream.name, downstream.slug) == ('Renamed', 'welcome')
        assert downstream.areas == {'body': Area(value='Changed')}

    def test_changed_slug_links_a_new_copy(self):
        upstream = _create_template(UPSTREAM)
        self._update(upstream)
        upstream.slug = 'renamed'
        upstream.save()

        self._update(upstream)

        slugs = Template.objects.filter(domain=DOWNSTREAM, is_linked=True).values_list('slug', flat=True)
        assert sorted(slugs) == ['renamed', 'welcome']

    def test_recreates_a_copy_deleted_downstream(self):
        upstream = _create_template(UPSTREAM)
        self._update(upstream)
        Template.objects.filter(domain=DOWNSTREAM).update(deleted=True)

        self._update(upstream)

        assert Template.objects.get(domain=DOWNSTREAM, deleted=False).is_linked

    def test_new_upstream_template_with_the_slug_of_a_deleted_one_replaces_the_copy(self):
        self._update(_create_template(UPSTREAM, areas={'body': Area(value='Old')}))
        Template.objects.filter(domain=UPSTREAM).update(deleted=True)

        self._update(_create_template(UPSTREAM, areas={'body': Area(value='New')}))

        downstream = Template.objects.get(domain=DOWNSTREAM)
        assert downstream.areas == {'body': Area(value='New')}

    def test_rejects_remote_link(self):
        upstream = _create_template(UPSTREAM)
        self.domain_link.remote_base_url = 'https://example.com'
        self.addCleanup(setattr, self.domain_link, 'remote_base_url', None)

        with pytest.raises(DomainLinkError, match='remote'):
            self._update(upstream)

    def test_rejects_template_from_another_domain(self):
        with pytest.raises(DomainLinkError, match='does not exist in the upstream domain'):
            self._update(_create_template('somewhere-else'))

    def test_rejects_template_deleted_upstream(self):
        with pytest.raises(DomainLinkError, match='does not exist in the upstream domain'):
            self._update(_create_template(UPSTREAM, deleted=True))

    def test_rejects_slug_used_downstream(self):
        local = _create_template(DOWNSTREAM)

        with pytest.raises(DomainLinkError, match='conflicts with an existing template'):
            self._update(_create_template(UPSTREAM))

        assert list(Template.objects.filter(domain=DOWNSTREAM)) == [local]

    def test_slug_used_downstream_does_not_get_the_images(self):
        _create_template(DOWNSTREAM)
        upstream = self._create_image_template(make_image())

        with pytest.raises(DomainLinkError, match='conflicts with an existing template'):
            self._update(upstream)

        assert not BlobMeta.objects.partitioned_query(DOWNSTREAM).filter(parent_id=DOWNSTREAM).exists()

    def _create_image_template(self, data):
        key = save_image(UPSTREAM, SimpleUploadedFile('logo.png', data))
        self.addCleanup(delete_image, key)
        return _create_template(UPSTREAM, areas={'logo': Area(type=AreaType.IMAGE, value=key)})

    def _update_image(self, upstream_template):
        self._update(upstream_template)
        key = Template.objects.get(domain=DOWNSTREAM).areas['logo'].value
        self.addCleanup(delete_image, key)
        return key

    def test_downstream_gets_a_copy_of_the_images(self):
        data = make_image()
        upstream = self._create_image_template(data)

        key = self._update_image(upstream)

        assert key != upstream.areas['logo'].value
        assert get_image_data(DOWNSTREAM, key) == data
        assert get_image(DOWNSTREAM, key).expires_on is None

    def test_later_links_expire_the_previous_copies(self):
        upstream = self._create_image_template(make_image())
        first_key = self._update_image(upstream)

        second_key = self._update_image(upstream)

        assert second_key != first_key
        assert get_image(DOWNSTREAM, first_key).expires_on is not None
        assert get_image(DOWNSTREAM, second_key).expires_on is None

    def test_rejects_missing_image(self):
        upstream = _create_template(UPSTREAM, areas={'logo': Area(type=AreaType.IMAGE, value='missing')})

        with pytest.raises(DomainLinkError, match='logo'):
            self._update(upstream)

        assert not Template.objects.filter(domain=DOWNSTREAM).exists()


class TestDocumentTemplateViewModels(TestCase):

    def test_templates_are_split_by_where_they_come_from(self):
        local = _create_template(DOWNSTREAM, slug='local')
        linked = _create_template(DOWNSTREAM, slug='linked', is_linked=True)
        _create_template(DOWNSTREAM, slug='gone', deleted=True)
        _create_template(DOWNSTREAM, slug='linked-gone', is_linked=True, deleted=True)

        upstream, downstream = get_upstream_and_downstream_document_templates(DOWNSTREAM)

        assert upstream == {'local': local}
        assert downstream == {'linked': linked}

    def test_pulled_template_shows_when_it_was_last_pulled(self):
        domain_link = DomainLink.link_domains(DOWNSTREAM, UPSTREAM)
        self.addCleanup(domain_link.delete)
        upstream = _create_template(UPSTREAM)
        update_linked_document_template(domain_link, upstream.slug)
        domain_link.update_last_pull(
            'document_template', 'user-id', model_detail={'upstream_slug': 'welcome'},
        )
        _, downstream = get_upstream_and_downstream_document_templates(DOWNSTREAM)

        view_models = build_pullable_view_models_from_data_models(
            DOWNSTREAM, domain_link, {}, {}, {}, {}, {}, {}, {}, downstream, pytz.UTC,
        )

        [view_model] = [vm for vm in view_models if vm['type'] == 'document_template']
        assert view_model['detail'] == {'upstream_slug': 'welcome'}
        assert isinstance(view_model['last_update'], (str, datetime))


@pytest.mark.parametrize('is_linked', [False, True])
def test_view_model_identifies_the_template_by_slug(is_linked):
    template = Template(name='Welcome', slug='welcome', is_linked=is_linked)

    view_model = build_document_template_view_model(template)

    assert view_model['type'] == 'document_template'
    assert view_model['name'] == 'Document Template (Welcome)'
    assert view_model['detail'] == {'upstream_slug': 'welcome'}


def test_no_view_model_without_template():
    assert build_document_template_view_model(None) is None
