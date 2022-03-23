from django.test import SimpleTestCase

from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.client import ElasticManageAdapter
from corehq.apps.es.cases import ElasticCase
from corehq.util.es.elasticsearch import TransportError

from ..es import CaseESView


class ElasticCase2(ElasticCase):

    type = "type2"
    mapping = ElasticCase().mapping  # TODO: remove with transient_util


@es_test
class TestESView(SimpleTestCase):

    def setUp(self):
        super().setUp()
        self.manager = ElasticManageAdapter()
        self.cases = ElasticCase()
        self._purge_indices()
        self.manager.index_create(self.cases.index_name)
        self.manager.index_put_mapping(self.cases.index_name, self.cases.type,
                                       self.cases.mapping)
        self.manager.index_put_alias(self.cases.index_name, CaseESView.es_alias)

    def tearDown(self):
        self._purge_indices()
        super().tearDown()

    def _purge_indices(self):
        try:
            self.manager.index_delete(self.cases.index_name)
        except TransportError:
            # TransportError(404, 'index_not_found_exception', 'no such index')
            pass

    def test_get_document_id_collision(self):
        """Because this is testing HQ's use of the Elasticsearch "Get API" in an
        ambiguous way (i.e. ``GET /<index>/_all/<doc_id>``), there is a chance
        that a regression bug that starts using ``_all`` in this way again may
        not cause this test to fail. It performs as expected right now, and the
        bug will be fixed soon.
        """

        def to_dict(dict_obj):
            return dict(dict_obj._data)

        def mk_doc(doc_id, location_id):
            return {"_id": doc_id, "domain": "some-domain",
                    "doc_type": CaseESView.doc_type, "location_id": location_id}

        # index a (case) doc with default _type ('case')
        doc_id = "1"
        doc_ny = mk_doc(doc_id, "NYC")
        self.cases.index(doc_ny, refresh=True)
        self.assertEqual(doc_ny, self.cases.get(doc_id))
        view = CaseESView(doc_ny["domain"])
        # test that the view fetches the doc by its ID as we'd expect
        self.assertEqual(doc_ny, to_dict(view.get_document(doc_id)))

        # index a doc with a new _type ('type2')
        cases_type2 = ElasticCase2()
        self.manager.index_put_mapping(cases_type2.index_name, cases_type2.type,
                                       cases_type2.mapping)
        doc_dc = mk_doc(doc_id, "DC")
        cases_type2.index(doc_dc, refresh=True)

        # test that the CaseESView still sees the doc it expects
        self.assertEqual(doc_ny, to_dict(view.get_document(doc_id)))
