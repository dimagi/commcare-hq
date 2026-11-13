from datetime import datetime

from django.test import TestCase

import pytest
import pytz

from corehq.apps.document_templates.images import get_image
from corehq.apps.document_templates.models import IMAGE, Area, Template
from corehq.apps.document_templates.tests.utils import delete_image, png_bytes
from corehq.apps.hqmedia.models import CommCareImage
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
        update_linked_document_template(self.domain_link, str(upstream_template.id))

    def test_first_link_copies_the_template(self):
        upstream = _create_template(UPSTREAM)

        self._update(upstream)

        downstream = Template.objects.get(domain=DOWNSTREAM)
        assert downstream.upstream_id == upstream.id
        assert (downstream.name, downstream.slug) == ('Welcome', 'welcome')
        assert downstream.areas == {'body': Area(value='Hello')}

    def test_later_links_update_the_copy(self):
        upstream = _create_template(UPSTREAM)
        self._update(upstream)
        upstream.name = 'Renamed'
        upstream.slug = 'renamed'
        upstream.areas = {'body': Area(value='Changed')}
        upstream.save()

        self._update(upstream)

        downstream = Template.objects.get(domain=DOWNSTREAM)
        assert (downstream.name, downstream.slug) == ('Renamed', 'renamed')
        assert downstream.areas == {'body': Area(value='Changed')}

    def test_restores_a_copy_deleted_downstream(self):
        upstream = _create_template(UPSTREAM)
        self._update(upstream)
        Template.objects.filter(domain=DOWNSTREAM).update(deleted=True)

        self._update(upstream)

        assert not Template.objects.get(domain=DOWNSTREAM).deleted

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

    def _create_image(self, domain):
        image = CommCareImage.get_by_data(png_bytes())
        image.attach_data(png_bytes(), original_filename='logo.png')
        image.add_domain(domain, owner=True)
        self.addCleanup(delete_image, image._id)
        return image._id

    def test_downstream_domain_can_use_the_images(self):
        image_id = self._create_image(UPSTREAM)
        upstream = _create_template(UPSTREAM, areas={'logo': Area(type=IMAGE, value=image_id)})

        self._update(upstream)

        assert Template.objects.get(domain=DOWNSTREAM).areas['logo'].value == image_id
        assert get_image(DOWNSTREAM, image_id)._id == image_id

    def test_rejects_image_the_upstream_domain_cannot_use(self):
        image_id = self._create_image('somewhere-else')
        upstream = _create_template(UPSTREAM, areas={'logo': Area(type=IMAGE, value=image_id)})

        with pytest.raises(DomainLinkError, match='logo'):
            self._update(upstream)

        assert not Template.objects.filter(domain=DOWNSTREAM).exists()
        assert DOWNSTREAM not in CommCareImage.get(image_id).valid_domains


class TestDocumentTemplateViewModels(TestCase):

    def test_templates_are_split_by_where_they_come_from(self):
        local = _create_template(DOWNSTREAM, slug='local')
        linked = _create_template(DOWNSTREAM, slug='linked', upstream_id=7)
        _create_template(DOWNSTREAM, slug='gone', deleted=True)
        _create_template(DOWNSTREAM, slug='linked-gone', upstream_id=8, deleted=True)

        upstream, downstream = get_upstream_and_downstream_document_templates(DOWNSTREAM)

        assert upstream == {str(local.id): local}
        assert downstream == {'7': linked}

    def test_pulled_template_shows_when_it_was_last_pulled(self):
        domain_link = DomainLink.link_domains(DOWNSTREAM, UPSTREAM)
        self.addCleanup(domain_link.delete)
        upstream = _create_template(UPSTREAM)
        update_linked_document_template(domain_link, str(upstream.id))
        domain_link.update_last_pull(
            'document_template', 'user-id', model_detail={'upstream_template_id': str(upstream.id)},
        )
        _, downstream = get_upstream_and_downstream_document_templates(DOWNSTREAM)

        view_models = build_pullable_view_models_from_data_models(
            DOWNSTREAM, domain_link, {}, {}, {}, {}, {}, {}, {}, downstream, pytz.UTC,
        )

        [view_model] = [vm for vm in view_models if vm['type'] == 'document_template']
        assert view_model['detail'] == {'upstream_template_id': str(upstream.id)}
        assert isinstance(view_model['last_update'], (str, datetime))


@pytest.mark.parametrize('upstream_id, expected', [(None, '3'), (7, '7')])
def test_view_model_identifies_the_upstream_template(upstream_id, expected):
    template = Template(id=3, name='Welcome', upstream_id=upstream_id)

    view_model = build_document_template_view_model(template)

    assert view_model['type'] == 'document_template'
    assert view_model['name'] == 'Document Template (Welcome)'
    assert view_model['detail'] == {'upstream_template_id': expected}


def test_no_view_model_without_template():
    assert build_document_template_view_model(None) is None
