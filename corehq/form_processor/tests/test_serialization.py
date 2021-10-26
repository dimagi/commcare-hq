import uuid

from django.db import router
from django.test import TestCase

from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
from corehq.form_processor.models import XFormInstanceSQL
from corehq.form_processor.tests.utils import (
    FormProcessorTestUtils,
    sharded,
)
from corehq.form_processor.utils import get_simple_form_xml
from corehq.sql_db.routers import HINT_PLPROXY


@sharded
class SerializationTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super(SerializationTests, cls).setUpClass()
        cls.domain = uuid.uuid4().hex

        cls.using = router.db_for_read(XFormInstanceSQL, **{HINT_PLPROXY: True})

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_xforms(cls.domain)
        super(SerializationTests, cls).tearDownClass()

    def test_serialize_attachments(self):
        form_id = uuid.uuid4().hex
        form_xml = get_simple_form_xml(form_id)
        submit_form_locally(form_xml, domain=self.domain)

        form = FormAccessorSQL().get_form(form_id)
        with self.assertNumQueries(1, using=form.db):
            # 1 query to fetch the form.xml attachment. The rest are lazy
            form_json = form.to_json(include_attachments=True)

        form_xml = form.get_attachment_meta('form.xml')

        with self.assertNumQueries(1, using=form.db):
            # lazy evaluation of attachments list
            self.assertEqual(form_json['external_blobs']['form.xml']['id'], str(form_xml.key))

        # this query goes through pl_proxy
        with self.assertNumQueries(1, using=form.db):
            # lazy evaluation of history
            self.assertEqual(0, len(form_json['history']))
