import uuid
from io import BytesIO

import pytest
from couchdbkit import ResourceNotFound
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.test import TestCase
from PIL import Image

from corehq.apps.document_templates.images import save_image
from corehq.apps.document_templates.models import Area, Template
from corehq.apps.document_templates.views import TemplateForm

from corehq.apps.hqmedia.models import CommCareImage

DOMAIN = 'document-templates-form-test'


def _form(data=None, area_names=(), **kwargs):
    return TemplateForm(data, domain=DOMAIN, area_names=area_names, **kwargs)


def test_area_fields_are_prefixed():
    form = _form(area_names=['area1', 'area2'])
    assert list(form.fields) == [
        'name', 'slug',
        'area_area1', 'area_area1_type', 'area_area1_image',
        'area_area2', 'area_area2_type', 'area_area2_image',
    ]


def test_area_named_like_a_form_field_does_not_collide():
    form = _form(area_names=['name', 'slug'])
    assert list(form.fields) == [
        'name', 'slug',
        'area_name', 'area_name_type', 'area_name_image',
        'area_slug', 'area_slug_type', 'area_slug_image',
    ]


@pytest.mark.parametrize('slug', ['has space', 'a/b', 'dot.slug', 'ünicode', 'x' * 51])
def test_invalid_slug_is_rejected(slug):
    form = _form({'name': 'Welcome', 'slug': slug}, area_names=[])
    assert not form.is_valid()
    assert 'slug' in form.errors


def test_areas_have_the_fields_of_each_area_only():
    form = _form(area_names=['area1', 'name'])
    assert [area.name for area in form.areas()] == ['area1', 'name']
    assert [area.markdown_field.name for area in form.areas()] == ['area_area1', 'area_name']
    assert [area.type_field.name for area in form.areas()] == ['area_area1_type', 'area_name_type']


def test_areas_render_as_bootstrap_textareas():
    html = str(_form(area_names=['area1'])['area_area1'])
    assert '<textarea' in html
    assert 'name="area_area1"' in html
    assert 'class="form-control"' in html


def test_initial_comes_from_the_instance():
    template = Template(name='Welcome', slug='welcome', areas={'body': Area(value='Hi')})
    form = _form(area_names=['body', 'footer'], instance=template)
    assert form['name'].value() == 'Welcome'
    assert form['slug'].value() == 'welcome'
    assert form['area_body'].value() == 'Hi'
    assert form['area_footer'].value() == ''


class TestTemplateFormValidation(TestCase):

    def test_name_and_slug_are_required(self):
        for missing in ['name', 'slug']:
            with self.subTest(missing=missing):
                data = {'name': 'Welcome', 'slug': 'welcome'}
                del data[missing]
                form = _form(data)
                assert not form.is_valid()
                assert missing in form.errors

    def test_valid_slug_is_accepted(self):
        for slug in ['welcome', 'welcome-2', 'welcome_2', 'WELCOME', 'x' * 50]:
            with self.subTest(slug=slug):
                assert _form({'name': 'Welcome', 'slug': slug}).is_valid()

    def test_areas_are_optional(self):
        form = _form({'name': 'Welcome', 'slug': 'welcome'}, area_names=['area1'])
        assert form.is_valid()
        assert form.get_areas() == {'area1': Area(value='')}

    def test_get_areas_uses_plain_names_as_keys(self):
        form = _form(
            {'name': 'Welcome', 'slug': 'welcome', 'area_area1': '# Hi', 'area_area2': 'Bye'},
            area_names=['area1', 'area2'],
        )
        assert form.is_valid()
        assert form.get_areas() == {
            'area1': Area(value='# Hi'),
            'area2': Area(value='Bye'),
        }

    def test_unknown_area_fields_are_ignored(self):
        form = _form(
            {'name': 'Welcome', 'slug': 'welcome', 'area_area1': 'Hi', 'area_unknown': 'x'},
            area_names=['area1'],
        )
        assert form.is_valid()
        assert form.get_areas() == {'area1': Area(value='Hi')}


    def test_duplicate_slug_is_rejected(self):
        Template.objects.create(domain=DOMAIN, name='Old', slug='welcome', areas={})
        form = _form({'name': 'Welcome', 'slug': 'welcome'})
        assert not form.is_valid()
        assert form.errors['slug'] == ['A template with this slug already exists.']

    def test_slug_of_a_deleted_template_can_be_reused(self):
        Template.objects.create(domain=DOMAIN, name='Old', slug='welcome', areas={}, deleted=True)
        assert _form({'name': 'Welcome', 'slug': 'welcome'}).is_valid()

    def test_slug_of_another_domain_can_be_reused(self):
        Template.objects.create(domain='other', name='Old', slug='welcome', areas={})
        assert _form({'name': 'Welcome', 'slug': 'welcome'}).is_valid()

    def test_template_can_keep_its_own_slug(self):
        template = Template.objects.create(domain=DOMAIN, name='Old', slug='welcome', areas={})
        assert _form({'name': 'Renamed', 'slug': 'welcome'}, instance=template).is_valid()

    def test_template_cannot_take_the_slug_of_another_template(self):
        Template.objects.create(domain=DOMAIN, name='Other', slug='taken', areas={})
        template = Template.objects.create(domain=DOMAIN, name='Old', slug='welcome', areas={})
        form = _form({'name': 'Old', 'slug': 'taken'}, instance=template)
        assert not form.is_valid()
        assert 'slug' in form.errors


class TestTemplateFormSave(TestCase):

    def test_creates_a_template_in_the_domain(self):
        form = _form({'name': 'Welcome', 'slug': 'welcome', 'area_body': 'Hi'}, area_names=['body'])
        assert form.is_valid()
        template = form.save()
        template.refresh_from_db()
        assert template.domain == DOMAIN
        assert (template.name, template.slug) == ('Welcome', 'welcome')
        assert template.areas == {'body': Area(value='Hi')}

    def test_updates_the_instance(self):
        template = Template.objects.create(
            domain=DOMAIN, name='Old', slug='old', areas={'body': Area(value='Old')},
        )
        form = _form(
            {'name': 'New', 'slug': 'new', 'area_body': 'New'}, area_names=['body'], instance=template,
        )
        assert form.is_valid()
        form.save()
        template.refresh_from_db()
        assert (template.name, template.slug) == ('New', 'new')
        assert template.areas == {'body': Area(value='New')}
        assert Template.objects.count() == 1


def _png():
    buffer = BytesIO()
    Image.new('RGB', (10, 20), color=tuple(uuid.uuid4().bytes[:3])).save(buffer, format='PNG')
    return buffer.getvalue()


def _delete_image(image_id):
    try:
        CommCareImage.get(image_id).delete()
    except ResourceNotFound:
        pass


class TestTemplateFormImages(TestCase):

    def _image_id(self, domain=DOMAIN):
        image_id = save_image(domain, SimpleUploadedFile('logo.png', _png()), 'user')
        self.addCleanup(_delete_image, image_id)
        return image_id

    def _data(self, **fields):
        return {'name': 'Welcome', 'slug': 'welcome', **fields}

    def test_image_area_saves_the_image_id(self):
        image_id = self._image_id()
        form = _form(
            self._data(area_header_type='image', area_header_image=image_id),
            area_names=['header'],
        )
        assert form.is_valid()
        assert form.get_areas() == {'header': Area(type='image', value=image_id)}

    def test_markdown_is_not_saved_for_an_image_area(self):
        image_id = self._image_id()
        form = _form(
            self._data(area_header='# Hi', area_header_type='image', area_header_image=image_id),
            area_names=['header'],
        )
        assert form.is_valid()
        assert form.get_areas() == {'header': Area(type='image', value=image_id)}

    def test_image_is_not_saved_for_a_markdown_area(self):
        form = _form(
            self._data(area_header='# Hi', area_header_type='markdown', area_header_image=self._image_id()),
            area_names=['header'],
        )
        assert form.is_valid()
        assert form.get_areas() == {'header': Area(type='markdown', value='# Hi')}

    def test_image_area_without_an_image_is_valid(self):
        form = _form(self._data(area_header_type='image'), area_names=['header'])
        assert form.is_valid()
        assert form.get_areas() == {'header': Area(type='image', value='')}

    def test_image_of_another_project_is_rejected(self):
        form = _form(
            self._data(area_header_type='image', area_header_image=self._image_id('other-domain')),
            area_names=['header'],
        )
        assert not form.is_valid()
        assert form.errors['area_header_image'] == ['The image does not belong to this project.']

    def test_image_that_does_not_exist_is_rejected(self):
        form = _form(
            self._data(area_header_type='image', area_header_image='missing'),
            area_names=['header'],
        )
        assert not form.is_valid()
        assert form.errors['area_header_image'] == ['The image does not exist.']

    def test_image_of_a_markdown_area_is_not_checked(self):
        form = _form(
            self._data(area_header_type='markdown', area_header_image='missing'),
            area_names=['header'],
        )
        assert form.is_valid()

    def test_unknown_type_is_rejected(self):
        form = _form(self._data(area_header_type='video'), area_names=['header'])
        assert not form.is_valid()
        assert 'area_header_type' in form.errors

    def test_initial_of_a_saved_image_area(self):
        template = Template(name='Welcome', slug='welcome', areas={'header': Area(type='image', value='abc')})
        form = _form(area_names=['header'], instance=template)
        assert form['area_header'].value() == ''
        assert form['area_header_type'].value() == 'image'
        assert form['area_header_image'].value() == 'abc'

    def test_areas_of_the_editor(self):
        template = Template(name='Welcome', slug='welcome', areas={'header': Area(type='image', value='abc')})
        header, footer = _form(area_names=['header', 'footer'], instance=template).areas()
        assert (header.type, header.image['image_id']) == ('image', 'abc')
        assert header.image['thumbnail_url'] == '/hq/multimedia/file/CommCareImage/abc/?thumb=120'
        assert (footer.type, footer.image['image_id'], footer.image['thumbnail_url']) == ('markdown', '', '')

    def test_editor_type_falls_back_to_markdown_for_a_posted_type_that_is_unknown(self):
        form = _form(self._data(area_header_type="');alert(1);('"), area_names=['header'])
        assert not form.is_valid()
        assert form.areas()[0].type == 'markdown'

    def test_editor_shows_the_error_of_an_image(self):
        form = _form(self._data(area_header_type='image', area_header_image='missing'), area_names=['header'])
        assert not form.is_valid()
        assert form.areas()[0].image['error'] == 'The image does not exist.'


def test_areas_of_the_editor_have_a_label_and_a_description_from_the_definitions():
    header, other = _form(area_names=['header', 'other']).areas()
    assert header.label == 'Header'
    assert header.description.startswith('7 x 1 in, at the top of the first page.')
    assert (other.label, other.description) == ('other', '')


def test_area_editor_shows_the_label_and_the_description():
    [area] = _form(area_names=['footer']).areas()
    html = render_to_string('document_templates/partials/area_editor.html', {'area': area, 'domain': DOMAIN})
    assert '>Footer</label' in html.replace('\n', '').replace('  ', '')
    assert 'at the bottom of every page.' in html


def test_area_editor_has_the_type_dropdown_and_both_fields():
    [area] = _form(area_names=['header']).areas()
    html = render_to_string('document_templates/partials/area_editor.html', {'area': area, 'domain': DOMAIN})
    assert "x-data=\"{ type: 'markdown' }\"" in html
    assert '<select name="area_header_type"' in html
    assert 'x-model="type"' in html
    assert '<textarea name="area_header"' in html
    assert 'name="area_header_image"' in html
    assert f'hx-post="/a/{DOMAIN}/document_templates/templates/images/header/"' in html
