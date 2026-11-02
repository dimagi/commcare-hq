import pytest
from django.test import TestCase

from corehq.apps.document_templates.models import Template, Variable
from corehq.apps.document_templates.views import TemplateForm

DOMAIN = 'document-templates-form-test'


def _form(data=None, variable_names=(), **kwargs):
    return TemplateForm(data, domain=DOMAIN, variable_names=variable_names, **kwargs)


def test_variable_fields_are_prefixed():
    form = _form(variable_names=['var1', 'var2'])
    assert list(form.fields) == ['name', 'slug', 'var_var1', 'var_var2']


def test_variable_named_like_a_form_field_does_not_collide():
    form = _form(variable_names=['name', 'slug'])
    assert list(form.fields) == ['name', 'slug', 'var_name', 'var_slug']


@pytest.mark.parametrize('slug', ['has space', 'a/b', 'dot.slug', 'ünicode', 'x' * 51])
def test_invalid_slug_is_rejected(slug):
    form = _form({'name': 'Welcome', 'slug': slug}, variable_names=[])
    assert not form.is_valid()
    assert 'slug' in form.errors


def test_variable_fields_excludes_name_and_slug():
    form = _form(variable_names=['var1', 'name'])
    assert [field.name for field in form.variable_fields()] == ['var_var1', 'var_name']


def test_variables_render_as_bootstrap_textareas():
    html = str(_form(variable_names=['var1'])['var_var1'])
    assert '<textarea' in html
    assert 'name="var_var1"' in html
    assert 'class="form-control"' in html


def test_initial_comes_from_the_instance():
    template = Template(name='Welcome', slug='welcome', variables={'body': Variable(value='Hi')})
    form = _form(variable_names=['body', 'footer'], instance=template)
    assert form['name'].value() == 'Welcome'
    assert form['slug'].value() == 'welcome'
    assert form['var_body'].value() == 'Hi'
    assert form['var_footer'].value() == ''


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

    def test_variables_are_optional(self):
        form = _form({'name': 'Welcome', 'slug': 'welcome'}, variable_names=['var1'])
        assert form.is_valid()
        assert form.get_variables() == {'var1': Variable(value='')}

    def test_get_variables_uses_plain_names_as_keys(self):
        form = _form(
            {'name': 'Welcome', 'slug': 'welcome', 'var_var1': '# Hi', 'var_var2': 'Bye'},
            variable_names=['var1', 'var2'],
        )
        assert form.is_valid()
        assert form.get_variables() == {
            'var1': Variable(value='# Hi'),
            'var2': Variable(value='Bye'),
        }

    def test_unknown_variable_fields_are_ignored(self):
        form = _form(
            {'name': 'Welcome', 'slug': 'welcome', 'var_var1': 'Hi', 'var_unknown': 'x'},
            variable_names=['var1'],
        )
        assert form.is_valid()
        assert form.get_variables() == {'var1': Variable(value='Hi')}


    def test_duplicate_slug_is_rejected(self):
        Template.objects.create(domain=DOMAIN, name='Old', slug='welcome', variables={})
        form = _form({'name': 'Welcome', 'slug': 'welcome'})
        assert not form.is_valid()
        assert form.errors['slug'] == ['A template with this slug already exists.']

    def test_slug_of_a_deleted_template_can_be_reused(self):
        Template.objects.create(domain=DOMAIN, name='Old', slug='welcome', variables={}, deleted=True)
        assert _form({'name': 'Welcome', 'slug': 'welcome'}).is_valid()

    def test_slug_of_another_domain_can_be_reused(self):
        Template.objects.create(domain='other', name='Old', slug='welcome', variables={})
        assert _form({'name': 'Welcome', 'slug': 'welcome'}).is_valid()

    def test_template_can_keep_its_own_slug(self):
        template = Template.objects.create(domain=DOMAIN, name='Old', slug='welcome', variables={})
        assert _form({'name': 'Renamed', 'slug': 'welcome'}, instance=template).is_valid()

    def test_template_cannot_take_the_slug_of_another_template(self):
        Template.objects.create(domain=DOMAIN, name='Other', slug='taken', variables={})
        template = Template.objects.create(domain=DOMAIN, name='Old', slug='welcome', variables={})
        form = _form({'name': 'Old', 'slug': 'taken'}, instance=template)
        assert not form.is_valid()
        assert 'slug' in form.errors


class TestTemplateFormSave(TestCase):

    def test_creates_a_template_in_the_domain(self):
        form = _form({'name': 'Welcome', 'slug': 'welcome', 'var_body': 'Hi'}, variable_names=['body'])
        assert form.is_valid()
        template = form.save()
        template.refresh_from_db()
        assert template.domain == DOMAIN
        assert (template.name, template.slug) == ('Welcome', 'welcome')
        assert template.variables == {'body': Variable(value='Hi')}

    def test_updates_the_instance(self):
        template = Template.objects.create(
            domain=DOMAIN, name='Old', slug='old', variables={'body': Variable(value='Old')},
        )
        form = _form(
            {'name': 'New', 'slug': 'new', 'var_body': 'New'}, variable_names=['body'], instance=template,
        )
        assert form.is_valid()
        form.save()
        template.refresh_from_db()
        assert (template.name, template.slug) == ('New', 'new')
        assert template.variables == {'body': Variable(value='New')}
        assert Template.objects.count() == 1
