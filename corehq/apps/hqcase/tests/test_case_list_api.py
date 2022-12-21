import datetime
import uuid
from base64 import b64decode
from unittest.mock import patch, MagicMock

from django.http import QueryDict
from django.test import TestCase

from casexml.apps.case.mock import CaseBlock, IndexAttrs

from corehq import privileges
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import (
    case_search_es_setup,
    case_search_es_teardown,
    es_test,
)
from corehq.apps.users.models import HQApiKey, HqPermissions, UserRole, WebUser
from corehq.util.test_utils import (
    flag_enabled,
    generate_cases,
    privilege_enabled,
)
from corehq.util.view_utils import reverse

from ..api.core import UserError
from ..api.get_list import MAX_PAGE_SIZE, get_list

GOOD_GUYS_ID = str(uuid.uuid4())
BAD_GUYS_ID = str(uuid.uuid4())


@es_test
@privilege_enabled(privileges.API_ACCESS)
@flag_enabled('CASE_API_V0_6')
@flag_enabled('API_THROTTLE_WHITELIST')
class TestCaseListAPI(TestCase):
    domain = 'test-case-list-api'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        case_search_es_setup(cls.domain, cls._get_case_blocks())
        role = UserRole.create(
            cls.domain, 'edit-data', permissions=HqPermissions(edit_data=True, access_api=True)
        )
        cls.web_user = WebUser.create(cls.domain, 'netflix', 'password', None, None, role_id=role.get_id)

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
        case_search_es_teardown()
        cls.domain_obj.delete()
        super().tearDownClass()

    def test_pagination(self):
        res = get_list(self.domain, {"limit": "3", "case_type": "person"})
        self.assertItemsEqual(res.keys(), ['next', 'cases', 'matching_records'])
        self.assertEqual(res['matching_records'], 5)
        self.assertEqual(
            ['mattie', 'rooster', 'laboeuf'],
            [c['external_id'] for c in res['cases']]
        )

        cursor = b64decode(res['next']['cursor']).decode('utf-8')
        self.assertIn('limit=3', cursor)
        self.assertIn('case_type=person', cursor)
        self.assertIn('indexed_on.gte', cursor)
        self.assertIn('last_case_id', cursor)

        res = get_list(self.domain, res['next'])
        self.assertEqual(res['matching_records'], 2)
        self.assertEqual(
            ['chaney', 'ned'],
            [c['external_id'] for c in res['cases']]
        )
        self.assertNotIn('next', res)  # No pages after this one

    def test_get_list_basic_auth(self):
        self.client.login(username='netflix', password='password')
        with patch('corehq.apps.hqcase.views.get_list', lambda *args: {'example': 'result'}):
            res = self.client.get(reverse('case_api', args=(self.domain,)))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {'example': 'result'})

    def test_GET_param_auth(self):
        # url/?username=foo&api_key=abc123
        # That is a valid means of authenticating, but we need to strip those
        # params so they're not interpreted as filters on the API
        api_key = HQApiKey.objects.create(user=self.web_user.get_django_user())
        get_list = MagicMock(return_value={'example': 'result'})
        with patch('corehq.apps.hqcase.views.get_list', get_list):
            get_params = {
                'username': 'netflix',
                'api_key': api_key.key,
                'external_id': 'mattie',
            }
            self.client.get(reverse('case_api', args=(self.domain,), params=get_params))

        domain, params = get_list.call_args.args
        # only 'external_id' should get passed through
        self.assertEqual(params, {'external_id': 'mattie'})


@generate_cases([
    ("", ['good_guys', 'bad_guys', 'mattie', 'rooster', 'laboeuf', 'chaney', 'ned']),
    ("limit=2", ['good_guys', 'bad_guys']),
    ("external_id=mattie", ['mattie']),
    ("external_id=the-man-with-no-name", []),
    ("case_type=team", ["good_guys", "bad_guys"]),
    ("owner_id=person_owner", ['mattie', 'rooster', 'laboeuf', 'chaney', 'ned']),
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
    params = QueryDict(querystring).dict()
    actual = [c['external_id'] for c in get_list(self.domain, params)['cases']]
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
        params = QueryDict(querystring).dict()
        get_list(self.domain, params)
    self.assertEqual(str(e.exception), error_msg)
