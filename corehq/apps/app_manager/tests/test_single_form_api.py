
from django.test import TestCase

from corehq.apps.app_manager.models import (
    Application,
    Module,
)
from corehq.apps.app_manager.tests.util import get_simple_form
from corehq.apps.app_manager.views.single_form_api import (
    FormResource,
    _form_resource_dict,
)

ENTITY_XML = (
    '<?xml version="1.0"?>\n'
    '<!DOCTYPE root [ <!ENTITY xxe SYSTEM "file:///etc/passwd"> ]>\n'
    '<h:html xmlns:h="http://www.w3.org/1999/xhtml"><h:head>'
    '<h:title>&xxe;</h:title></h:head><h:body/></h:html>'
)


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


# ``case_in_form`` locks /data/question2; changing its bind changes the
# question's signature, which is what the locked-question check compares.
LOCKED_BIND = '<bind nodeset="/data/question2" type="xsd:string" vellum:lock="all" />'
EDITED_LOCKED_BIND = (
    '<bind nodeset="/data/question2" type="xsd:string" constraint="0" vellum:lock="all" />'
)
