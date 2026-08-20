from unittest import mock

from django.test import TestCase

from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.tests.util import get_simple_form
from corehq.apps.app_manager.views.single_form_api import (
    FORM_API_APP_NOT_FOUND,
    FORM_API_FORM_NOT_FOUND,
    FORM_API_MODULE_NOT_FOUND,
    ApiError,
    FormResource,
    _form_resource_dict,
    get_form_for_api,
)
from corehq.apps.domain.shortcuts import create_domain


class GetFormForApiTests(TestCase):
    def setUp(self):
        self.domain = create_domain('form-api-get-domain')
        self.addCleanup(self.domain.delete)
        self.app = Application.new_app(self.domain.name, 'Test App')
        module = self.app.add_module(Module.new_module('Module One', lang='en'))
        self.form = module.new_form('Form One', lang='en', attachment=get_simple_form(xmlns='xmlns-1'))
        self.module_id = module.unique_id
        self.form_id = self.form.unique_id
        self.app.save()
        self.addCleanup(self.app.delete)

    def test_returns_form_on_success(self):
        form, result = get_form_for_api(self.domain.name, self.app._id, self.module_id, self.form_id)

        assert result.success is True
        assert result.errors == []
        assert form.unique_id == self.form_id

    def test_treats_missing_app_as_not_found(self):
        form, result = get_form_for_api(self.domain.name, 'missing-app', self.module_id, self.form_id)

        assert result.success is False
        assert result.errors == [ApiError(FORM_API_APP_NOT_FOUND, mock.ANY)]

    def test_treats_saved_build_as_not_found(self):
        build = self.app.make_build()
        build.save()
        self.addCleanup(build.delete)

        form, result = get_form_for_api(self.domain.name, build._id, self.module_id, self.form_id)

        assert result.success is False
        assert result.errors == [ApiError(FORM_API_APP_NOT_FOUND, mock.ANY)]

    def test_returns_module_not_found(self):
        form, result = get_form_for_api(self.domain.name, self.app._id, 'missing-module', self.form_id)

        assert result.success is False
        assert result.errors == [ApiError(FORM_API_MODULE_NOT_FOUND, mock.ANY)]

    def test_returns_form_not_found(self):
        form, result = get_form_for_api(self.domain.name, self.app._id, self.module_id, 'missing-form')

        assert result.success is False
        assert result.errors[0].error == FORM_API_FORM_NOT_FOUND


class FormResourceEtagTests(TestCase):
    def setUp(self):
        self.app = Application.new_app('form-etag-domain', 'Test App')
        module = self.app.add_module(Module.new_module('Module One', lang='en'))
        self.form = module.new_form('Form One', lang='en', attachment=get_simple_form(xmlns='xmlns-1'))
        self.app.save()
        self.addCleanup(self.app.delete)

    def test_stable_across_reloading_unchanged_form(self):
        reloaded = Application.get(self.app._id).get_form(self.form.unique_id)
        assert FormResource(self.form).get_etag() == FormResource(reloaded).get_etag()

    def test_changes_when_form_content_changes(self):
        before = FormResource(self.form).get_etag()
        self.form.name = {'en': 'Renamed'}
        after = FormResource(self.form).get_etag()
        assert before != after

    def test_is_a_quoted_string(self):
        etag = FormResource(self.form).get_etag()
        assert etag.startswith('"') and etag.endswith('"')


class FormResourceDictTests(TestCase):
    def setUp(self):
        app = Application.new_app('form-resource-dict-domain', 'Test App')
        module = app.add_module(Module.new_module('Module One', lang='en'))
        self.form = module.new_form('Form One', lang='en', attachment=get_simple_form(xmlns='xmlns-1'))

    def test_includes_source_key(self):
        resource = _form_resource_dict(self.form)
        assert resource['source'] == self.form.source

    def test_does_not_include_validation_cache(self):
        # Assigning validation_cache also writes a dynamic property onto
        # the document, so every in-memory form carries the key while one
        # reloaded from Couch has it stripped by FormBase.wrap. Leaving it
        # in the resource would give one unchanged form two ETags.
        self.form.set_validation_cache('some cached value')
        resource = _form_resource_dict(self.form)
        assert 'validation_cache' not in resource

    def test_includes_form_json_fields(self):
        resource = _form_resource_dict(self.form)
        assert resource['unique_id'] == self.form.unique_id
        assert resource['name'] == self.form.name
