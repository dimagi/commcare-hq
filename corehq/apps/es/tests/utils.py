import json

from nose.plugins.attrib import attr
from nose.tools import nottest

from pillowtop.es_utils import initialize_index_and_mapping
from pillowtop.tests.utils import TEST_INDEX_INFO

from corehq.elastic import ES_META, get_es_new, send_to_elasticsearch
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.case_search import transform_case_for_elasticsearch
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup


class ElasticTestMixin(object):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._es_instance = get_es_new()
        initialize_index_and_mapping(cls._es_instance, TEST_INDEX_INFO)

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(TEST_INDEX_INFO.index)
        super().tearDownClass()

    def validate_query(self, query):
        if 'query' not in query:
            return
        # only query portion can be validated using ES validate API
        query = {'query': query.pop('query', {})}
        validation = self._es_instance.indices.validate_query(body=query, index=TEST_INDEX_INFO.index, params={'explain': 'true'})
        self.assertTrue(validation['valid'])

    def checkQuery(self, query, json_output, is_raw_query=False, validate_query=True):
        self.maxDiff = None
        if is_raw_query:
            raw_query = query
        else:
            raw_query = query.raw_query
        msg = "Expected Query:\n{}\nGenerated Query:\n{}".format(
            json.dumps(json_output, indent=4),
            json.dumps(raw_query, indent=4),
        )
        # NOTE: This makes it [a, b, c] == [b, c, a] which shouldn't matter in ES queries
        json_output = json.loads(json.dumps(json_output))
        raw_query = json.loads(json.dumps(raw_query))
        self.assertEqual(raw_query, json_output, msg=msg)
        if validate_query:
            # some queries need more setup to validate like initializing the specific index
            #   that they are querying.
            self.validate_query(raw_query)


@nottest
def es_test(test):
    """Decorator for tagging ElasticSearch tests

    :param test: A test class, method, or function.
    """
    return attr(es_test=True)(test)


def populate_es_index(models, index_name, doc_prep_fn=lambda doc: doc):
    index_info = ES_META[index_name]
    es = get_es_new()
    with trap_extra_setup(ConnectionError):
        initialize_index_and_mapping(es, index_info)
    for model in models:
        send_to_elasticsearch(
            index_name,
            doc_prep_fn(model.to_json() if hasattr(model, 'to_json') else model)
        )
    es.indices.refresh(index_info.index)


def populate_user_index(users):
    populate_es_index(users, 'users')


def case_search_es_setup(domain, case_blocks):
    """Submits caseblocks, creating the cases, then sends them to ES"""
    from corehq.apps.hqcase.utils import submit_case_blocks
    xform, cases = submit_case_blocks([cb.as_text() for cb in case_blocks], domain=domain)
    assert not xform.is_error, xform
    order = {cb.case_id: index for index, cb in enumerate(case_blocks)}
    # send cases to ES in the same order they were passed in so `indexed_on`
    # order is predictable for TestCaseListAPI.test_pagination and others
    cases = sorted(cases, key=lambda case: order[case.case_id])
    populate_es_index(cases, 'case_search', transform_case_for_elasticsearch)


def case_search_es_teardown():
    FormProcessorTestUtils.delete_all_cases()
    ensure_index_deleted(CASE_SEARCH_INDEX_INFO.index)
