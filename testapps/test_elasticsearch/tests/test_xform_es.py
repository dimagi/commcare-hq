import uuid
import datetime
from django.test import SimpleTestCase
from corehq.pillows.xform import XFormPillow
from couchforms.models import XFormInstance
from pillowtop.tests import require_explicit_elasticsearch_testing


class XFormESTestCase(SimpleTestCase):

    @classmethod
    @require_explicit_elasticsearch_testing
    def setUpClass(cls):
        cls.domain = 'xform-es-tests'
        cls.now = datetime.datetime.utcnow()
        cls.forms = [
            XFormInstance(_id=uuid.uuid4().hex,
                          received_on=cls.now - datetime.timedelta(days=10)),
            XFormInstance(_id=uuid.uuid4().hex, received_on=cls.now)
        ]
        cls.pillow = XFormPillow()
        for form in cls.forms:
            form.domain = cls.domain
            cls.pillow.change_transport(form.to_json())

    @classmethod
    def tearDownClass(cls):
        for form in cls.forms:
            cls.pillow.get_es_new().delete(cls.pillow.es_index, cls.pillow.es_type, form._id)

    def test_forms_are_in_index(self):
        for form in self.forms:
            self.assertTrue(self.pillow.doc_exists(form.form_id))
