import pytest
from django.test import TestCase

from corehq.apps.document_templates.models import Area, Template
from corehq.apps.document_templates.views import TemplateForm

DOMAIN = 'document-templates-form-test'


def _form(data=None, area_names=(), **kwargs):
    return TemplateForm(data, domain=DOMAIN, area_names=area_names, **kwargs)


def test_area_fields_are_prefixed():
    form = _form(area_names=['area1', 'area2'])
    assert list(form.fields) == ['name', 'slug', 'area_area1', 'area_area2']


def test_area_named_like_a_form_field_does_not_collide():
    form = _form(area_names=['name', 'slug'])
    assert list(form.fields) == ['name', 'slug', 'area_name', 'area_slug']


@pytest.mark.parametrize('slug', ['has space', 'a/b', 'dot.slug', 'ünicode', 'x' * 51])
def test_invalid_slug_is_rejected(slug):
    form = _form({'name': 'Welcome', 'slug': slug}, area_names=[])
    assert not form.is_valid()
    assert 'slug' in form.errors


def test_area_fields_excludes_name_and_slug():
    form = _form(area_names=['area1', 'name'])
    assert [field.name for field in form.area_fields()] == ['area_area1', 'area_name']


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
