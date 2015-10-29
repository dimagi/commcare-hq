import uuid
from django.test import TestCase, SimpleTestCase
from casexml.apps.case.exceptions import IllegalCaseId
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.xform import CaseDbCache
from casexml.apps.case.xml import V2
from corehq.form_processor.interfaces.processor import FormProcessorInterface


class CaseDbCacheTest(TestCase):
    """
    Tests the functionality of the CaseDbCache object
    """

    def testDomainCheck(self):
        id = uuid.uuid4().hex
        FormProcessorInterface().post_case_blocks([
                CaseBlock(
                    create=True, case_id=id,
                    user_id='some-user'
                ).as_xml()
            ], {'domain': 'good-domain'}
        )
        bad_cache = CaseDbCache(domain='bad-domain')
        try:
            bad_cache.get(id)
            self.fail('domain security check failed to raise exception')
        except IllegalCaseId:
            pass

        good_cache = CaseDbCache(domain='good-domain')
        case = good_cache.get(id)
        self.assertEqual('some-user', case.user_id) # just sanity check it's the right thing

    def testDocTypeCheck(self):
        id = uuid.uuid4().hex
        CommCareCase.get_db().save_doc({
            "_id": id,
            "doc_type": "AintNoCasesHere"
        })
        cache = CaseDbCache()
        try:
            cache.get(id)
            self.fail('doc type security check failed to raise exception')
        except IllegalCaseId:
            pass

        doc_back = CommCareCase.get_db().get(id)
        self.assertEqual("AintNoCasesHere", doc_back['doc_type'])

    def testGetPopulatesCache(self):
        case_ids = _make_some_cases(3)
        cache = CaseDbCache()
        for id in case_ids:
            self.assertFalse(cache.in_cache(id))

        for i, id in enumerate(case_ids):
            case = cache.get(id)
            self.assertEqual(str(i), case.my_index)

        for id in case_ids:
            self.assertTrue(cache.in_cache(id))

    def testSetPopulatesCache(self):
        case_ids = _make_some_cases(3)
        cache = CaseDbCache()
        for id in case_ids:
            self.assertFalse(cache.in_cache(id))

        for id in case_ids:
            cache.set(id, CommCareCase.get(id))

        for i, id in enumerate(case_ids):
            self.assertTrue(cache.in_cache(id))
            case = cache.get(id)
            self.assertEqual(str(i), case.my_index)

    def testPopulate(self):
        case_ids = _make_some_cases(3)
        cache = CaseDbCache()
        for id in case_ids:
            self.assertFalse(cache.in_cache(id))

        cache.populate(case_ids)
        for id in case_ids:
            self.assertTrue(cache.in_cache(id))

        #  sanity check
        for i, id in enumerate(case_ids):
            case = cache.get(id)
            self.assertEqual(str(i), case.my_index)

    def testStripHistory(self):
        case_ids = _make_some_cases(3)

        history_cache = CaseDbCache()
        for i, id in enumerate(case_ids):
            self.assertFalse(history_cache.in_cache(id))
            case = history_cache.get(id)
            self.assertEqual(str(i), case.my_index)
            self.assertTrue(len(case.actions) > 0)

        nohistory_cache = CaseDbCache(strip_history=True)
        for i, id in enumerate(case_ids):
            self.assertFalse(nohistory_cache.in_cache(id))
            case = nohistory_cache.get(id)
            self.assertEqual(str(i), case.my_index)
            self.assertTrue(len(case.actions) == 0)

        more_case_ids = _make_some_cases(3)
        history_cache.populate(more_case_ids)
        nohistory_cache.populate(more_case_ids)

        for i, id in enumerate(more_case_ids):
            self.assertTrue(history_cache.in_cache(id))
            case = history_cache.get(id)
            self.assertEqual(str(i), case.my_index)
            self.assertTrue(len(case.actions) > 0)

        for i, id in enumerate(more_case_ids):
            self.assertTrue(nohistory_cache.in_cache(id))
            case = nohistory_cache.get(id)
            self.assertEqual(str(i), case.my_index)
            self.assertTrue(len(case.actions) == 0)

    def test_nowrap(self):
        case_ids = _make_some_cases(1)
        cache = CaseDbCache(wrap=False)
        case = cache.get(case_ids[0])
        self.assertTrue(isinstance(case, dict))
        self.assertFalse(isinstance(case, CommCareCase))


class CaseDbCacheNoDbTest(SimpleTestCase):

    def test_wrap_lock_dependency(self):
        # valid combinations
        CaseDbCache(domain='some-domain', lock=False, wrap=True)
        CaseDbCache(domain='some-domain', lock=False, wrap=False)
        CaseDbCache(domain='some-domain', lock=True, wrap=True)
        with self.assertRaises(ValueError):
            # invalid
            CaseDbCache(domain='some-domain', lock=True, wrap=False)


def _make_some_cases(howmany, domain='dbcache-test'):
    ids = [uuid.uuid4().hex for i in range(howmany)]
    FormProcessorInterface().post_case_blocks([
        CaseBlock(
            create=True,
            case_id=ids[i],
            user_id='some-user',
            update={
                'my_index': i,
            }
        ).as_xml() for i in range(howmany)
    ], {'domain': domain})
    return ids
