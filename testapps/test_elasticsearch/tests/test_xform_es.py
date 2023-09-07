import datetime
from unittest.mock import patch
import uuid
from collections import namedtuple

from django.test import SimpleTestCase

from corehq.apps.es.client import manager
from corehq.apps.es.forms import FormES, form_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.form_processor.utils import TestFormMetadata
from corehq.util.test_utils import make_es_ready_form

WrappedJsonFormPair = namedtuple('WrappedJsonFormPair', ['wrapped_form', 'json_form'])


@es_test(requires=[form_adapter])
class XFormESTestCase(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(XFormESTestCase, cls).setUpClass()
        cls.forms = []

    def setUp(self):
        super(XFormESTestCase, self).setUp()
        self.test_id = uuid.uuid4().hex

    @classmethod
    def _ship_forms_to_es(cls, metadatas):
        with patch('corehq.pillows.utils.get_user_type', return_value='CommCareUser'):
            for form_metadata in metadatas:
                form_metadata = form_metadata or TestFormMetadata()
                form_pair = make_es_ready_form(form_metadata)
                cls.forms.append(form_pair)
                form_adapter.index(form_pair.json_form)
        # have to refresh the index to make sure changes show up
        manager.index_refresh(form_adapter.index_name)

    @classmethod
    def tearDownClass(cls):
        cls.forms = []
        super(XFormESTestCase, cls).tearDownClass()

    def test_forms_are_in_index(self):
        for form in self.forms:
            self.assertFalse(form_adapter.exists(form.wrapped_form.form_id))
        self._ship_forms_to_es([None, None])
        self.assertEqual(2, len(self.forms))
        for form in self.forms:
            self.assertTrue(form_adapter.exists(form.wrapped_form.form_id))

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
