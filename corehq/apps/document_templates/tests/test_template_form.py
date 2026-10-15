import pytest

from corehq.apps.document_templates.views import TemplateForm


def test_variable_fields_are_prefixed():
    form = TemplateForm(variable_names=['var1', 'var2'])
    assert list(form.fields) == ['name', 'slug', 'var_var1', 'var_var2']


def test_variable_named_like_a_form_field_does_not_collide():
    form = TemplateForm(variable_names=['name', 'slug'])
    assert list(form.fields) == ['name', 'slug', 'var_name', 'var_slug']


@pytest.mark.parametrize('missing', ['name', 'slug'])
def test_name_and_slug_are_required(missing):
    data = {'name': 'Welcome', 'slug': 'welcome'}
    del data[missing]
    form = TemplateForm(data, variable_names=[])
    assert not form.is_valid()
    assert missing in form.errors


@pytest.mark.parametrize('slug', ['has space', 'a/b', 'dot.slug', 'ünicode', 'x' * 51])
def test_invalid_slug_is_rejected(slug):
    form = TemplateForm({'name': 'Welcome', 'slug': slug}, variable_names=[])
    assert not form.is_valid()
    assert 'slug' in form.errors


@pytest.mark.parametrize('slug', ['welcome', 'welcome-2', 'welcome_2', 'WELCOME', 'x' * 50])
def test_valid_slug_is_accepted(slug):
    form = TemplateForm({'name': 'Welcome', 'slug': slug}, variable_names=[])
    assert form.is_valid()


def test_variables_are_optional():
    form = TemplateForm({'name': 'Welcome', 'slug': 'welcome'}, variable_names=['var1'])
    assert form.is_valid()
    assert form.get_variables() == {'var1': {'type': 'markdown', 'value': ''}}


def test_get_variables_uses_plain_names_as_keys():
    form = TemplateForm(
        {'name': 'Welcome', 'slug': 'welcome', 'var_var1': '# Hi', 'var_var2': 'Bye'},
        variable_names=['var1', 'var2'],
    )
    assert form.is_valid()
    assert form.get_variables() == {
        'var1': {'type': 'markdown', 'value': '# Hi'},
        'var2': {'type': 'markdown', 'value': 'Bye'},
    }


def test_variable_fields_excludes_name_and_slug():
    form = TemplateForm(variable_names=['var1', 'name'])
    assert [field.name for field in form.variable_fields()] == ['var_var1', 'var_name']


def test_variables_render_as_bootstrap_textareas():
    html = str(TemplateForm(variable_names=['var1'])['var_var1'])
    assert '<textarea' in html
    assert 'name="var_var1"' in html
    assert 'class="form-control"' in html


def test_duplicate_slug_is_rejected():
    form = TemplateForm(
        {'name': 'Welcome', 'slug': 'welcome'}, variable_names=[], existing_slugs=['welcome'],
    )
    assert not form.is_valid()
    assert form.errors['slug'] == ['A template with this slug already exists.']


def test_unused_slug_is_accepted_when_others_exist():
    form = TemplateForm(
        {'name': 'Welcome', 'slug': 'welcome'}, variable_names=[], existing_slugs=['other'],
    )
    assert form.is_valid()


def test_unknown_variable_fields_are_ignored():
    form = TemplateForm(
        {'name': 'Welcome', 'slug': 'welcome', 'var_var1': 'Hi', 'var_unknown': 'x'},
        variable_names=['var1'],
    )
    assert form.is_valid()
    assert form.get_variables() == {'var1': {'type': 'markdown', 'value': 'Hi'}}
