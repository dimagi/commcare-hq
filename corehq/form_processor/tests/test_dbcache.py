import uuid
from django.test import TestCase, SimpleTestCase
from casexml.apps.case.exceptions import IllegalCaseId
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import post_case_blocks
from corehq.form_processor.backends.sql.casedb import CaseDbCacheSQL
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.tests.utils import sharded


@sharded
class CaseDbCacheTest(TestCase):
    """
    Tests the functionality of the CaseDbCache object
    """

    def setUp(self):
        super(CaseDbCacheTest, self).setUp()
        self.interface = FormProcessorInterface()

    def testDomainCheck(self):
        id = uuid.uuid4().hex
        post_case_blocks([
                CaseBlock.deprecated_init(
                    create=True, case_id=id,
                    user_id='some-user'
                ).as_xml()
            ], {'domain': 'good-domain'}
        )
        bad_cache = self.interface.casedb_cache(domain='bad-domain')
        try:
            bad_cache.get(id)
            self.fail('domain security check failed to raise exception')
        except IllegalCaseId:
            pass
        good_cache = self.interface.casedb_cache(domain='good-domain')
        case = good_cache.get(id)
        self.assertEqual('some-user', case.user_id) # just sanity check it's the right thing

    def testGetPopulatesCache(self):
        case_ids = _make_some_cases(3)
        cache = self.interface.casedb_cache()
        for id in case_ids:
            self.assertFalse(cache.in_cache(id))

        for i, id in enumerate(case_ids):
            case = cache.get(id)
            self.assertEqual(str(i), case.dynamic_case_properties()['my_index'])

        for id in case_ids:
            self.assertTrue(cache.in_cache(id))

    def testSetPopulatesCache(self):
        case_ids = _make_some_cases(3)
        cache = self.interface.casedb_cache()
        for id in case_ids:
            self.assertFalse(cache.in_cache(id))

        for id in case_ids:
            cache.set(id, CaseAccessors().get_case(id))

        for i, id in enumerate(case_ids):
            self.assertTrue(cache.in_cache(id))
            case = cache.get(id)
            self.assertEqual(str(i), case.dynamic_case_properties()['my_index'])

    def testPopulate(self):
        case_ids = _make_some_cases(3)
        cache = self.interface.casedb_cache()
        for id in case_ids:
            self.assertFalse(cache.in_cache(id))

        cache.populate(case_ids)
        for id in case_ids:
            self.assertTrue(cache.in_cache(id))

        #  sanity check
        for i, id in enumerate(case_ids):
            case = cache.get(id)
            self.assertEqual(str(i), case.dynamic_case_properties()['my_index'])


class CaseDbCacheNoDbTest(SimpleTestCase):

    def test_sql_wrap_support(self):
        CaseDbCacheSQL(domain='some-domain', wrap=True)
        with self.assertRaises(ValueError):
            # invalid
            CaseDbCacheSQL(domain='some-domain', wrap=False)


def _make_some_cases(howmany, domain='dbcache-test'):
    ids = [uuid.uuid4().hex for i in range(howmany)]
    post_case_blocks([
        CaseBlock.deprecated_init(
            create=True,
            case_id=ids[i],
            user_id='some-user',
            update={
                'my_index': i,
            }
        ).as_xml() for i in range(howmany)
    ], {'domain': domain})
    return ids
