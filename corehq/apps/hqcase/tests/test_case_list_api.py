import datetime
import uuid
from base64 import b64decode
from unittest.mock import Mock

from django.http import QueryDict
from django.test import TestCase

from casexml.apps.case.mock import CaseBlock, IndexAttrs

from corehq import privileges
from corehq.apps.es.tests.utils import (
    case_search_es_setup,
    es_test,
)
from corehq.apps.es.case_search import case_search_adapter
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.util.test_utils import generate_cases, privilege_enabled
from corehq.apps.data_dictionary.models import CaseType

from ..api.core import UserError
from ..api.get_list import MAX_PAGE_SIZE, get_list

GOOD_GUYS_ID = str(uuid.uuid4())
BAD_GUYS_ID = str(uuid.uuid4())


@es_test(requires=[case_search_adapter], setup_class=True)
@privilege_enabled(privileges.API_ACCESS)
class TestCaseListAPI(TestCase):
    domain = 'test-case-list-api'
    couch_user = Mock(has_permission=lambda domain, permission: True)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        case_search_es_setup(cls.domain, cls._get_case_blocks())
        cls.case_type_obj = CaseType(domain=cls.domain, name='person')
        cls.case_type_obj.save()

    @staticmethod
    def _get_case_blocks():
        case_blocks = []
        for team_id, name in [(GOOD_GUYS_ID, 'good_guys'), (BAD_GUYS_ID, 'bad_guys')]:
            case_blocks.append(CaseBlock(
                case_id=team_id,
                case_type='team',
                case_name=name,
                external_id=name,
                owner_id='team_owner',
                create=True,
            ))

        date_opened = datetime.datetime(1878, 2, 17, 12)
        for external_id, name, properties, team_id in [
                ('mattie', "Mattie Ross", {}, GOOD_GUYS_ID),
                ('rooster', "Reuben Cogburn", {"alias": "Rooster"}, GOOD_GUYS_ID),
                ('laboeuf', "LaBoeuf", {"alias": ""}, GOOD_GUYS_ID),
                ('chaney', "Tom Chaney", {"alias": "The Coward"}, BAD_GUYS_ID),
                ('ned', "Ned Pepper", {"alias": "Lucky Ned"}, BAD_GUYS_ID),
        ]:
            case_blocks.append(CaseBlock(
                case_id=str(uuid.uuid4()),
                case_type='person',
                case_name=name,
                external_id=external_id,
                owner_id='person_owner',
                date_opened=date_opened,
                create=True,
                update=properties,
                index={'parent': IndexAttrs('team', team_id, 'child')}
            ))
            date_opened += datetime.timedelta(days=1)

        case_blocks[-1].close = True  # close Ned Pepper
        return case_blocks

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases()
        cls.case_type_obj.delete()
        super().tearDownClass()

    def test_pagination(self):
        query_dict = QueryDict('limit=3&case_type=person&case_type=household')
        res = get_list(self.domain, self.couch_user, query_dict)
        self.assertItemsEqual(res.keys(), ['next', 'cases', 'matching_records'])
        self.assertEqual(res['matching_records'], 5)
        self.assertEqual(
            ['mattie', 'rooster', 'laboeuf'],
            [c['external_id'] for c in res['cases']]
        )

        cursor = b64decode(res['next']['cursor']).decode('utf-8')
        self.assertIn('limit=3', cursor)
        self.assertIn('case_type=person', cursor)
        self.assertIn('case_type=household', cursor)
        self.assertIn('indexed_on.gte', cursor)
        self.assertIn('last_case_id', cursor)

        res = get_list(self.domain, self.couch_user, res['next'])
        self.assertEqual(res['matching_records'], 2)
        self.assertEqual(
            ['chaney', 'ned'],
            [c['external_id'] for c in res['cases']]
        )
        self.assertNotIn('next', res)  # No pages after this one

    def test_deprecated_case_type(self):
        self.case_type_obj.is_deprecated = True
        self.case_type_obj.save()

        query_dict = QueryDict('')
        res = get_list(self.domain, self.couch_user, query_dict)
        self.assertEqual(res['matching_records'], 7)
        self.assertNotIn('next', res)

        query_dict = QueryDict('include_deprecated=True')
        res = get_list(self.domain, self.couch_user, query_dict)
        self.assertEqual(res['matching_records'], 7)

        query_dict = QueryDict('include_deprecated=False')
        res = get_list(self.domain, self.couch_user, query_dict)
        self.assertEqual(res['matching_records'], 2)


@generate_cases([
    ("", ['good_guys', 'bad_guys', 'mattie', 'rooster', 'laboeuf', 'chaney', 'ned']),
    ("limit=2", ['good_guys', 'bad_guys']),
    ("external_id=mattie", ['mattie']),
    ("external_id=the-man-with-no-name", []),
    ("case_type=team", ["good_guys", "bad_guys"]),
    ("owner_id=person_owner", ['mattie', 'rooster', 'laboeuf', 'chaney', 'ned']),
    ("owner_id=person_owner&owner_id=team_owner",
     ['good_guys', 'bad_guys', 'mattie', 'rooster', 'laboeuf', 'chaney', 'ned']),
    ("case_name=Mattie Ross", ["mattie"]),
    ("case_name=Mattie+Ross", ["mattie"]),
    ("case_name=Mattie", []),
    ("closed=true", ["ned"]),
    ("date_opened.lt=1878-02-19", ["mattie", "rooster"]),
    ("date_opened.lte=1878-02-19", ["mattie", "rooster", "laboeuf"]),
    ("date_opened.lte=1878-02-19T00:00:00", ["mattie", "rooster"]),
    ("date_opened.gt=1878-02-18&date_opened.lt=1878-02-20", ["laboeuf"]),
    ("date_opened.gt=1878-02-19T11:00:00&date_opened.lt=1878-02-19T13:00:00", ["laboeuf"]),
    ("date_opened.gt=1878-02-19T08:00:00-03:00&date_opened.lt=1878-02-19T10:00:00-03:00", ["laboeuf"]),
    ("date_opened.lt=1878-02-18&date_opened.gt=1878-02-19", []),
    ("properties.alias=Rooster", ["rooster"]),
    ("properties.alias=rooster", []),
    ('properties.foo {"test": "json"}=bar', []),  # This is escaped as expected
    ('properties.foo={"test": "json"}', []),  # This is escaped as expected
    ("case_type=person&properties.alias=", ["mattie", "laboeuf"]),
    ('query=(alias="Rooster" or name="Mattie Ross")', ["mattie", "rooster"]),
    (f"indices.parent={GOOD_GUYS_ID}", ['mattie', 'rooster', 'laboeuf']),
], TestCaseListAPI)
def test_case_list_queries(self, querystring, expected):
    params = QueryDict(querystring)
    case_list = get_list(self.domain, self.couch_user, params)
    actual = [c['external_id'] for c in case_list['cases']]
    # order matters, so this doesn't use assertItemsEqual
    self.assertEqual(actual, expected)


@generate_cases([
    ("limit=nolimitz", "'nolimitz' is not a valid value for 'limit'"),
    (f"limit={MAX_PAGE_SIZE + 2}", f"You cannot request more than {MAX_PAGE_SIZE} cases per request."),
    ("date_opened.lt=bad-datetime", "Cannot parse datetime 'bad-datetime'"),
    ("date_opened.lt=2020-02-30", "Cannot parse datetime '2020-02-30'"),
    ("password=1234", "'password' is not a valid parameter."),
    ("case_name.gte=a", "'case_name.gte' is not a valid parameter."),
    ("date_opened=2020-01-30", "'date_opened' is not a valid parameter."),
    ("date_opened.start=2020-01-30", "'start' is not a valid type of date range."),
    ('query=gibberish',
     "Bad query: Your search query is required to have at least one boolean "
     "operator (=, !=, >, >=, <, <=)"),
], TestCaseListAPI)
def test_bad_requests(self, querystring, error_msg):
    with self.assertRaises(UserError) as e:
        params = QueryDict(querystring)
        get_list(self.domain, self.couch_user, params)
    self.assertEqual(str(e.exception), error_msg)
