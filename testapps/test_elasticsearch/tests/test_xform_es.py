from collections import namedtuple
import uuid
import datetime
from django.test import SimpleTestCase
from corehq.apps.es import FormES
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.tests import get_simple_form_data
from corehq.form_processor.utils import convert_xform_to_json
from corehq.pillows.xform import XFormPillow
from pillowtop.tests import require_explicit_elasticsearch_testing


WrappedJsonFormPair = namedtuple('WrappedJsonFormPair', ['wrapped_form', 'json_form'])


class XFormESTestCase(SimpleTestCase):

    @classmethod
    @require_explicit_elasticsearch_testing
    def setUpClass(cls):
        cls.domain = 'xform-es-tests-{}'.format(uuid.uuid4().hex)
        cls.now = datetime.datetime.utcnow()
        cls.forms = [
            _make_es_ready_form(cls.domain),
            _make_es_ready_form(cls.domain),
        ]
        cls.pillow = XFormPillow()
        for form_pair in cls.forms:
            cls.pillow.change_transport(form_pair.json_form)

        # have to refresh the index to make sure changes show up
        cls.pillow.get_es_new().indices.refresh(cls.pillow.es_index)

    @classmethod
    def tearDownClass(cls):
        for form in cls.forms:
            cls.pillow.get_es_new().delete(cls.pillow.es_index, cls.pillow.es_type, form.wrapped_form.form_id)

    def test_forms_are_in_index(self):
        for form in self.forms:
            self.assertTrue(self.pillow.doc_exists(form.wrapped_form.form_id))

    def test_query_by_domain(self):
        query_set = FormES().domain(self.domain).run()
        self.assertEqual(2, query_set.total)
        self.assertEqual(set([f.wrapped_form.form_id for f in self.forms]), set(query_set.doc_ids))


def _make_es_ready_form(domain):
    # this is rather complicated due to form processor abstractions and ES restrictions
    # on what data needs to be in the index and is allowed in the index
    form_id = uuid.uuid4().hex
    form_xml = get_simple_form_data(form_id=form_id)
    form_json = convert_xform_to_json(form_xml)
    wrapped_form = FormProcessorInterface(domain=domain).new_xform(form_json)
    wrapped_form.domain = domain
    json_form = wrapped_form.to_json()
    json_form['form']['meta'].pop('appVersion')  # hack - ES chokes on this
    return WrappedJsonFormPair(wrapped_form, json_form)
