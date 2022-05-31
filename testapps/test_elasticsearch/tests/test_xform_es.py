from collections import namedtuple
import uuid
import datetime
from django.test import SimpleTestCase
from corehq.util.es.elasticsearch import ConnectionError

from corehq.apps.es import FormES
from corehq.apps.es.tests.utils import es_test
from corehq.elastic import get_es_new, send_to_elasticsearch, doc_exists_in_es
from corehq.form_processor.utils import TestFormMetadata
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.util.es.interface import ElasticsearchInterface
from corehq.util.test_utils import make_es_ready_form, trap_extra_setup
from pillowtop.es_utils import initialize_index_and_mapping

WrappedJsonFormPair = namedtuple('WrappedJsonFormPair', ['wrapped_form', 'json_form'])


@es_test
class XFormESTestCase(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(XFormESTestCase, cls).setUpClass()
        cls.now = datetime.datetime.utcnow()
        cls.forms = []
        with trap_extra_setup(ConnectionError):
            cls.es = get_es_new()
            initialize_index_and_mapping(cls.es, XFORM_INDEX_INFO)

    def setUp(self):
        super(XFormESTestCase, self).setUp()
        self.test_id = uuid.uuid4().hex

    @classmethod
    def _ship_forms_to_es(cls, metadatas):
        for form_metadata in metadatas:
            form_metadata = form_metadata or TestFormMetadata()
            form_pair = make_es_ready_form(form_metadata)
            cls.forms.append(form_pair)
            send_to_elasticsearch('forms', form_pair.json_form)
        # have to refresh the index to make sure changes show up
        cls.es.indices.refresh(XFORM_INDEX_INFO.alias)

    @classmethod
    def tearDownClass(cls):
        interface = ElasticsearchInterface(cls.es)
        for form in cls.forms:
            interface.delete_doc(XFORM_INDEX_INFO.alias, XFORM_INDEX_INFO.type, form.wrapped_form.form_id)
        cls.es.indices.refresh(XFORM_INDEX_INFO.alias)
        cls.forms = []
        super(XFormESTestCase, cls).tearDownClass()

    def test_forms_are_in_index(self):
        for form in self.forms:
            self.assertFalse(doc_exists_in_es(XFORM_INDEX_INFO, form.wrapped_form.form_id))
        self._ship_forms_to_es([None, None])
        self.assertEqual(2, len(self.forms))
        for form in self.forms:
            self.assertTrue(doc_exists_in_es(XFORM_INDEX_INFO, form.wrapped_form.form_id))

    def test_query_by_domain(self):
        domain1 = 'test1-{}'.format(self.test_id)
        domain2 = 'test2-{}'.format(self.test_id)
        self._ship_forms_to_es(
            2 * [TestFormMetadata(domain=domain1)] +
            1 * [TestFormMetadata(domain=domain2)]
        )
        self.assertEqual(2, FormES().domain(domain1).run().total)
        self.assertEqual(1, FormES().domain(domain2).run().total)

    def test_query_by_user(self):
        domain = 'test-by-user-{}'.format(self.test_id)
        user1 = 'user1-{}'.format(self.test_id)
        user2 = 'user2-{}'.format(self.test_id)
        self._ship_forms_to_es(
            2 * [TestFormMetadata(domain=domain, user_id=user1)] +
            1 * [TestFormMetadata(domain=domain, user_id=user2)]
        )
        self.assertEqual(2, FormES().user_id([user1]).run().total)
        self.assertEqual(1, FormES().user_id([user2]).run().total)
        self.assertEqual(3, FormES().user_id([user1, user2]).run().total)
        # also test with domain filter
        self.assertEqual(3, FormES().domain(domain).run().total)
        self.assertEqual(2, FormES().domain(domain).user_id([user1]).run().total)
        self.assertEqual(1, FormES().domain(domain).user_id([user2]).run().total)
        self.assertEqual(3, FormES().domain(domain).user_id([user1, user2]).run().total)

    def test_query_completed_date(self):
        domain = 'test-completed-{}'.format(self.test_id)
        early = datetime.datetime(2015, 12, 5)
        later = datetime.datetime(2015, 12, 8)
        self._ship_forms_to_es(
            2 * [TestFormMetadata(domain=domain, time_end=early)] +
            1 * [TestFormMetadata(domain=domain, time_end=later)]
        )
        base_qs = FormES().domain(domain)
        self.assertEqual(3, base_qs.run().total)
        # test gt/gte
        self.assertEqual(3, base_qs.completed(gt=early - datetime.timedelta(days=1)).run().total)
        self.assertEqual(3, base_qs.completed(gte=early).run().total)
        self.assertEqual(1, base_qs.completed(gt=early).run().total)
        self.assertEqual(1, base_qs.completed(gte=later).run().total)
        self.assertEqual(0, base_qs.completed(gt=later).run().total)
        # test lt/lte
        self.assertEqual(3, base_qs.completed(lt=later + datetime.timedelta(days=1)).run().total)
        self.assertEqual(3, base_qs.completed(lte=later).run().total)
        self.assertEqual(2, base_qs.completed(lt=later).run().total)
        self.assertEqual(2, base_qs.completed(lte=early).run().total)
        self.assertEqual(0, base_qs.completed(lt=early).run().total)
        # test both
        self.assertEqual(0, base_qs.completed(gt=early, lt=later).run().total)
