from unittest.mock import patch, Mock
from datetime import datetime
import pytz
import uuid

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from testil import eq
from freezegun import freeze_time

from corehq.apps.reports.tasks import summarize_user_counts
from corehq.apps.reports.util import get_user_id_from_form, datespan_from_beginning
from corehq.form_processor.exceptions import XFormNotFound
from corehq.form_processor.models import XFormInstance
from corehq.form_processor.utils import TestFormMetadata
from corehq.util.test_utils import get_form_ready_to_save
from corehq.apps.reports.standard.cases.utils import get_user_type
from corehq.apps.data_interfaces.deduplication import DEDUPE_XMLNS
from corehq.apps.domain.models import Domain
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es import case_search_adapter
from corehq.form_processor.models import CommCareCase
from corehq.apps.reports.util import domain_copied_cases_by_owner
from corehq.apps.users.models import CommCareUser
from corehq.apps.hqcase.case_helper import CaseCopier

DOMAIN = 'test_domain'
USER_ID = "5bc1315c-da6f-466d-a7c4-4580bc84a7b9"


@freeze_time("2023-02-10")
class TestDateSpanFromBeginning(SimpleTestCase):
    def test_start_and_end_date_dont_change_in_utc(self):
        start_time = datetime(year=2020, month=4, day=5)

        domain = Domain(date_created=start_time)
        datespan = datespan_from_beginning(domain, pytz.utc)

        self.assertEqual(datespan.startdate, datetime(year=2020, month=4, day=5))
        self.assertEqual(datespan.enddate, datetime(year=2023, month=2, day=10))

    def test_start_and_end_date_can_change_if_behind_utc(self):
        start_time = datetime(year=2020, month=4, day=5)

        domain = Domain(date_created=start_time)
        # POSIX timezones represent GMT+1 as 1 hour BEHIND GMT.
        datespan = datespan_from_beginning(domain, pytz.timezone('Etc/GMT+1'))

        self.assertEqual(datespan.startdate, datetime(year=2020, month=4, day=4))
        self.assertEqual(datespan.enddate, datetime(year=2023, month=2, day=9))


class TestSummarizeUserCounts(SimpleTestCase):
    def test_summarize_user_counts(self):
        self.assertEqual(
            summarize_user_counts({'a': 1, 'b': 10, 'c': 2}, n=0),
            {(): 13},
        )
        self.assertEqual(
            summarize_user_counts({'a': 1, 'b': 10, 'c': 2}, n=1),
            {'b': 10, (): 3},
        )
        self.assertEqual(
            summarize_user_counts({'a': 1, 'b': 10, 'c': 2}, n=2),
            {'b': 10, 'c': 2, (): 1},
        )
        self.assertEqual(
            summarize_user_counts({'a': 1, 'b': 10, 'c': 2}, n=3),
            {'a': 1, 'b': 10, 'c': 2, (): 0},
        )
        self.assertEqual(
            summarize_user_counts({'a': 1, 'b': 10, 'c': 2}, n=4),
            {'a': 1, 'b': 10, 'c': 2, (): 0},
        )


class TestGetUserType(SimpleTestCase):
    def setUp(self):
        self.form = Mock(
            xmlns='my-xmlns',
            metadata=Mock(
                userID=None,
                username='foobar'
            )
        )

    def test_unknown_user(self):
        self.assertEqual(get_user_type(self.form), 'Unknown')

    def test_system_user(self):
        self.form.metadata.username = 'system'
        self.assertEqual(get_user_type(self.form), 'System')

    def test_system_update(self):
        self.form.metadata.username = 'system'
        self.form.xmlns = DEDUPE_XMLNS
        self.assertEqual(get_user_type(self.form), 'Deduplication Rule')

    @patch(
        'corehq.apps.reports.standard.cases.utils.get_doc_info_by_id',
        return_value=Mock(type_display='Foobar')
    )
    def test_display_user(self, _):
        self.form.metadata.userID = '1234'
        self.assertEqual(get_user_type(self.form), 'Foobar')


def test_get_user_id():
    form_id = "acca290f-22fc-4c5c-8cce-ee253ca5678b"
    reset_cache(form_id)
    with patch.object(XFormInstance.objects, "get_form", get_form):
        eq(get_user_id_from_form(form_id), USER_ID)


def test_get_user_id_cached():
    form_id = "d1667406-319f-4d0c-9091-0d6c0032363a"
    reset_cache(form_id, USER_ID)
    with patch.object(XFormInstance.objects, "get_form", form_not_found):
        eq(get_user_id_from_form(form_id), USER_ID)


def test_get_user_id_not_found():
    form_id = "73bfc6a5-c66e-4b17-be6d-45513511e1ef"
    reset_cache(form_id)
    with patch.object(XFormInstance.objects, "get_form", form_not_found):
        eq(get_user_id_from_form(form_id), None)

    with patch.object(XFormInstance.objects, "get_form", get_form):
        # null value should not be cached
        eq(get_user_id_from_form(form_id), USER_ID)


def get_form(form_id):
    metadata = TestFormMetadata(domain="test", user_id=USER_ID)
    return get_form_ready_to_save(metadata, form_id=form_id)


def form_not_found(form_id):
    raise XFormNotFound(form_id)


def reset_cache(form_id, value=None):
    key = f'xform-{form_id}-user_id'
    if value is None:
        cache.delete(key)
    else:
        cache.set(key, value, 5)


@es_test(requires=[case_search_adapter])
class TestDomainCopiedCasesByOwner(TestCase):

    @classmethod
    def setUpClass(cls):
        super()
        cls.user = CommCareUser.create(DOMAIN, 'user', 'password', None, None)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(deleted_by_domain=None, deleted_by=None)
        super()

    def test_no_copied_cases_for_owner(self):
        self.assertEqual(domain_copied_cases_by_owner(DOMAIN, self.user.user_id), [])

    def test_user_have_no_copied_cases(self):
        _ = self._send_case_to_es(
            domain=DOMAIN,
            owner_id=self.user.user_id,
        )
        self.assertEqual(domain_copied_cases_by_owner(DOMAIN, self.user.user_id), [])

    def test_user_have_copied_cases(self):
        case = self._send_case_to_es(
            domain=DOMAIN,
            owner_id=self.user.user_id,
            is_copy=True,
        )
        self.assertEqual(domain_copied_cases_by_owner(DOMAIN, self.user.user_id), [case.case_id])

    def _send_case_to_es(
        self,
        domain=None,
        owner_id=None,
        is_copy=False,
    ):
        case_json = {}
        if is_copy:
            case_json[CaseCopier.COMMCARE_CASE_COPY_PROPERTY_NAME] = 'case_id'

        case = CommCareCase(
            case_id=uuid.uuid4().hex,
            domain=domain,
            owner_id=owner_id,
            type='case_type',
            case_json=case_json,
        )

        case_search_adapter.index(case, refresh=True)
        return case
