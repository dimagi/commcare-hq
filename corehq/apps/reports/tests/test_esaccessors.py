from __future__ import absolute_import
from __future__ import unicode_literals
import pytz
import uuid
from mock import patch

from datetime import datetime, timedelta
from django.test import SimpleTestCase, TestCase
from django.test.utils import override_settings

from corehq.apps.hqcase.utils import SYSTEM_FORM_XMLNS
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.form_processor.models import CommCareCaseSQL, CaseTransaction
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.pillows.mappings.case_mapping import CASE_INDEX, CASE_INDEX_INFO
from corehq.pillows.mappings.group_mapping import GROUP_INDEX_INFO
from corehq.pillows.mappings.ledger_mapping import LEDGER_INDEX_INFO
from corehq.pillows.mappings.user_mapping import USER_INDEX, USER_INDEX_INFO
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from dimagi.utils.dates import DateSpan
from dimagi.utils.parsing import string_to_utc_datetime
from elasticsearch.exceptions import ConnectionError

from corehq.util.elastic import ensure_index_deleted
from corehq.apps.users.models import CommCareUser
from corehq.apps.groups.models import Group
from corehq.blobs.mixin import BlobMetaRef
from corehq.form_processor.utils import TestFormMetadata
from casexml.apps.case.models import CommCareCase, CommCareCaseAction
from casexml.apps.case.const import CASE_ACTION_CREATE
from corehq.pillows.xform import transform_xform_for_elasticsearch
from corehq.pillows.utils import MOBILE_USER_TYPE, WEB_USER_TYPE
from corehq.pillows.case import transform_case_for_elasticsearch
from corehq.apps.reports.analytics.dbaccessors import get_aggregated_ledger_values
from corehq.apps.reports.analytics.esaccessors import (
    get_submission_counts_by_user,
    get_completed_counts_by_user,
    get_submission_counts_by_date,
    get_active_case_counts_by_owner,
    get_total_case_counts_by_owner,
    get_case_counts_closed_by_user,
    get_case_counts_opened_by_user,
    get_paged_forms_by_type,
    get_last_form_submissions_by_user,
    get_user_stubs,
    get_group_stubs,
    get_forms,
    get_form_counts_by_user_xmlns,
    get_form_duration_stats_by_user,
    get_form_duration_stats_for_users,
    get_last_form_submission_for_xmlns,
    guess_form_name_from_submissions_using_xmlns,
    get_all_user_ids_submitted,
    get_username_in_last_form_user_id_submitted,
    get_form_ids_having_multimedia,
    scroll_case_names,
    get_case_types_for_domain_es,
)
from corehq.apps.es.aggregations import MISSING_KEY
from corehq.util.test_utils import make_es_ready_form, trap_extra_setup
from pillowtop.es_utils import initialize_index_and_mapping
import six


class BaseESAccessorsTest(TestCase):
    es_index_info = None

    def setUp(self):
        super(BaseESAccessorsTest, self).setUp()
        with trap_extra_setup(ConnectionError):
            self.es = get_es_new()
            self._delete_es_index()
            self.domain = uuid.uuid4().hex
            if isinstance(self.es_index_info, (list, tuple)):
                for index_info in self.es_index_info:
                    initialize_index_and_mapping(self.es, index_info)
            else:
                initialize_index_and_mapping(self.es, self.es_index_info)

    def tearDown(self):
        self._delete_es_index()
        super(BaseESAccessorsTest, self).tearDown()

    def _delete_es_index(self):
        if isinstance(self.es_index_info, (list, tuple)):
            for index_info in self.es_index_info:
                ensure_index_deleted(index_info.index)
        else:
            ensure_index_deleted(self.es_index_info.index)


class TestFormESAccessors(BaseESAccessorsTest):

    es_index_info = [XFORM_INDEX_INFO, GROUP_INDEX_INFO]

    def _send_form_to_es(
            self,
            domain=None,
            completion_time=None,
            received_on=None,
            attachment_dict=None,
            **metadata_kwargs):
        attachment_dict = attachment_dict or {}
        metadata = TestFormMetadata(
            domain=domain or self.domain,
            time_end=completion_time or datetime.utcnow(),
            received_on=received_on or datetime.utcnow(),
        )
        for attr, value in metadata_kwargs.items():
            setattr(metadata, attr, value)

        form_pair = make_es_ready_form(metadata)
        if attachment_dict:
            form_pair.wrapped_form.external_blobs = {name: BlobMetaRef(**meta)
                for name, meta in six.iteritems(attachment_dict)}
            form_pair.json_form['external_blobs'] = attachment_dict

        es_form = transform_xform_for_elasticsearch(form_pair.json_form)
        send_to_elasticsearch('forms', es_form)
        self.es.indices.refresh(XFORM_INDEX_INFO.index)
        return form_pair

    def _send_group_to_es(self, _id=None, users=None):
        group = Group(
            domain=self.domain,
            name='narcos',
            users=users or [],
            case_sharing=False,
            reporting=False,
            _id=_id or uuid.uuid4().hex,
        )
        send_to_elasticsearch('groups', group.to_json())
        self.es.indices.refresh(GROUP_INDEX_INFO.index)
        return group

    @run_with_all_backends
    def test_get_forms(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)
        xmlns = 'http://a.b.org'
        app_id = '1234'
        user_id = 'abc'

        self._send_form_to_es(
            app_id=app_id,
            xmlns=xmlns,
            received_on=datetime(2013, 7, 2),
            user_id=user_id,
        )

        paged_result = get_forms(
            self.domain,
            start,
            end,
            user_ids=[user_id],
            app_ids=app_id,
            xmlnss=xmlns,
        )
        self.assertEqual(paged_result.total, 1)
        self.assertEqual(paged_result.hits[0]['xmlns'], xmlns)
        self.assertEqual(paged_result.hits[0]['form']['meta']['userID'], user_id)
        self.assertEqual(paged_result.hits[0]['received_on'], '2013-07-02T00:00:00.000000Z')

    @run_with_all_backends
    def test_get_form_ids_having_multimedia(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)
        xmlns = 'http://a.b.org'
        app_id = '1234'
        user_id = 'abc'

        self._send_form_to_es(
            app_id=app_id,
            xmlns=xmlns,
            received_on=datetime(2013, 7, 2),
            user_id=user_id,
            attachment_dict={
                'my_image': {'content_type': 'image/jpg'}
            }
        )

        # Decoy form
        self._send_form_to_es(
            app_id=app_id,
            xmlns=xmlns,
            received_on=datetime(2013, 7, 2),
            user_id=user_id,
        )

        form_ids = get_form_ids_having_multimedia(
            self.domain,
            app_id,
            xmlns,
            DateSpan(start, end),
            [],
        )
        self.assertEqual(len(form_ids), 1)

    @run_with_all_backends
    def test_get_form_ids_having_multimedia_with_user_types(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)
        xmlns = 'http://a.b.org'
        app_id = '1234'
        user_id = 'abc'

        with patch('corehq.pillows.xform.get_user_type', lambda _: MOBILE_USER_TYPE):
            self._send_form_to_es(
                app_id=app_id,
                xmlns=xmlns,
                received_on=datetime(2013, 7, 2),
                user_id=user_id,
                attachment_dict={
                    'my_image': {'content_type': 'image/jpg'}
                }
            )

        with patch('corehq.pillows.xform.get_user_type', lambda _: WEB_USER_TYPE):
            self._send_form_to_es(
                app_id=app_id,
                xmlns=xmlns,
                received_on=datetime(2013, 7, 2),
                user_id=user_id,
                attachment_dict={
                    'my_image': {'content_type': 'image/jpg'}
                }
            )

        form_ids = get_form_ids_having_multimedia(
            self.domain,
            app_id,
            xmlns,
            DateSpan(start, end),
            [MOBILE_USER_TYPE]
        )
        self.assertEqual(len(form_ids), 1)

        form_ids = get_form_ids_having_multimedia(
            self.domain,
            app_id,
            xmlns,
            DateSpan(start, end),
            [MOBILE_USER_TYPE, WEB_USER_TYPE]
        )
        self.assertEqual(len(form_ids), 2)

        form_ids = get_form_ids_having_multimedia(
            self.domain,
            app_id,
            xmlns,
            DateSpan(start, end),
            []
        )
        self.assertEqual(len(form_ids), 2)

    @run_with_all_backends
    def test_get_forms_multiple_apps_xmlnss(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)
        xmlns1, xmlns2 = 'http://a.b.org', 'http://b.c.org'
        app_id1, app_id2 = '1234', '4567'
        user_id = 'abc'

        self._send_form_to_es(
            app_id=app_id1,
            xmlns=xmlns1,
            received_on=datetime(2013, 7, 2),
            user_id=user_id,
        )
        self._send_form_to_es(
            app_id=app_id2,
            xmlns=xmlns2,
            received_on=datetime(2013, 7, 2),
            user_id=user_id,
        )
        self._send_form_to_es(
            app_id=app_id1,
            xmlns=xmlns1,
            received_on=datetime(2013, 7, 2),
            user_id=None,
        )

        paged_result = get_forms(
            self.domain,
            start,
            end,
            user_ids=[user_id],
            app_ids=[app_id1, app_id2],
            xmlnss=[xmlns1, xmlns2],
        )
        self.assertEqual(paged_result.total, 2)

        paged_result = get_forms(
            self.domain,
            start,
            end,
            user_ids=[user_id],
            app_ids=[app_id1, app_id2],
            xmlnss=[xmlns1],
        )
        self.assertEqual(paged_result.total, 1)

        paged_result = get_forms(
            self.domain,
            start,
            end,
            user_ids=[user_id],
            app_ids=[app_id1],
            xmlnss=[xmlns2],
        )
        self.assertEqual(paged_result.total, 0)

        paged_result = get_forms(
            self.domain,
            start,
            end,
            user_ids=[None],
            app_ids=[app_id1],
            xmlnss=[xmlns1],
        )
        self.assertEqual(paged_result.total, 1)

    @run_with_all_backends
    def test_basic_completed_by_user(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)

        self._send_form_to_es(completion_time=datetime(2013, 7, 2))

        results = get_completed_counts_by_user(self.domain, DateSpan(start, end))
        self.assertEquals(results['cruella_deville'], 1)

    @run_with_all_backends
    def test_completed_out_of_range_by_user(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)

        self._send_form_to_es(completion_time=datetime(2013, 8, 2))
        self._send_form_to_es(completion_time=datetime(2013, 7, 2))

        results = get_completed_counts_by_user(self.domain, DateSpan(start, end))
        self.assertEquals(results['cruella_deville'], 1)

    def test_completed_different_domain_by_user(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)

        self._send_form_to_es(completion_time=datetime(2013, 7, 3), domain='not-in-my-backyard')
        self._send_form_to_es(completion_time=datetime(2013, 7, 2))

        results = get_completed_counts_by_user(self.domain, DateSpan(start, end))
        self.assertEquals(results['cruella_deville'], 1)

    @run_with_all_backends
    def test_basic_submission_by_user(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)
        received_on = datetime(2013, 7, 15)

        self._send_form_to_es(received_on=received_on)

        results = get_submission_counts_by_user(self.domain, DateSpan(start, end))
        self.assertEquals(results['cruella_deville'], 1)

    @run_with_all_backends
    def test_get_last_form_submission_by_xmlns(self):
        xmlns = 'http://a.b.org'
        kwargs = {
            'user_id': 'u1',
            'app_id': '1234',
            'domain': self.domain,
        }

        first = datetime(2013, 7, 15, 0, 0, 0)
        second = datetime(2013, 7, 16, 0, 0, 0)
        third = datetime(2013, 7, 17, 0, 0, 0)

        self._send_form_to_es(received_on=second, xmlns=xmlns, **kwargs)
        self._send_form_to_es(received_on=third, xmlns=xmlns, **kwargs)
        self._send_form_to_es(received_on=first, xmlns=xmlns, **kwargs)

        form = get_last_form_submission_for_xmlns(self.domain, xmlns)
        self.assertEqual(string_to_utc_datetime(form['received_on']), third)

        form = get_last_form_submission_for_xmlns(self.domain, 'missing')
        self.assertIsNone(form)

    @run_with_all_backends
    def test_guess_form_name_from_xmlns_not_found(self):
        self.assertEqual(None, guess_form_name_from_submissions_using_xmlns('missing', 'missing'))

    @run_with_all_backends
    def test_guess_form_name_from_xmlns(self):
        form_name = 'my cool form'
        xmlns = 'http://a.b.org'
        self._send_form_to_es(
            xmlns=xmlns,
            form_name=form_name,
        )
        self.assertEqual(form_name, guess_form_name_from_submissions_using_xmlns(self.domain, xmlns))

    @run_with_all_backends
    def test_submission_out_of_range_by_user(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)

        self._send_form_to_es(received_on=datetime(2013, 8, 15))

        self._send_form_to_es(received_on=datetime(2013, 7, 15))

        results = get_submission_counts_by_user(self.domain, DateSpan(start, end))
        self.assertEquals(results['cruella_deville'], 1)

    @run_with_all_backends
    def test_submission_different_domain_by_user(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)
        received_on = datetime(2013, 7, 15)

        self._send_form_to_es(received_on=received_on)
        self._send_form_to_es(received_on=received_on, domain='not-in-my-backyard')

        results = get_submission_counts_by_user(self.domain, DateSpan(start, end))
        self.assertEquals(results['cruella_deville'], 1)

    @run_with_all_backends
    def test_basic_submission_by_date(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)
        received_on = datetime(2013, 7, 15)

        self._send_form_to_es(received_on=received_on)
        self._send_form_to_es(received_on=received_on, xmlns=SYSTEM_FORM_XMLNS)

        results = get_submission_counts_by_date(
            self.domain,
            ['cruella_deville'],
            DateSpan(start, end),
            pytz.utc
        )
        self.assertEquals(results['2013-07-15'], 1)

    @run_with_all_backends
    def test_get_paged_forms_by_type(self):
        self._send_form_to_es()
        self._send_form_to_es()

        paged_result = get_paged_forms_by_type(self.domain, ['xforminstance'], size=1)
        self.assertEqual(len(paged_result.hits), 1)
        self.assertEqual(paged_result.total, 2)

    @run_with_all_backends
    def test_timezone_differences(self):
        """
        Our received_on dates are always in UTC, so if we submit a form right at midnight UTC, then the report
        should show that form being submitted the day before if viewing from an earlier timezone like New York
        """
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)
        received_on = datetime(2013, 7, 15, 0, 0, 0)
        timezone = pytz.timezone('America/New_York')

        self._send_form_to_es(received_on=received_on)

        results = get_submission_counts_by_date(
            self.domain,
            ['cruella_deville'],
            DateSpan(start, end),
            timezone
        )
        self.assertEquals(results['2013-07-14'], 1)

    @run_with_all_backends
    def test_get_last_form_submission_for_user_for_app(self):
        kwargs_u1 = {
            'user_id': 'u1',
            'app_id': '1234',
            'domain': self.domain,
        }
        kwargs_u2 = {
            'user_id': 'u2',
            'app_id': '1234',
            'domain': self.domain,
        }
        kwargs_u3 = {
            'user_id': None,
            'app_id': '1234',
            'domain': self.domain,
        }

        first = datetime(2013, 7, 15, 0, 0, 0)
        second = datetime(2013, 7, 16, 0, 0, 0)
        third = datetime(2013, 7, 17, 0, 0, 0)

        self._send_form_to_es(received_on=second, xmlns='second', **kwargs_u1)
        self._send_form_to_es(received_on=third, xmlns='third', **kwargs_u1)
        self._send_form_to_es(received_on=first, xmlns='first', **kwargs_u1)

        self._send_form_to_es(received_on=second, xmlns='second', **kwargs_u2)
        self._send_form_to_es(received_on=third, xmlns='third', **kwargs_u2)
        self._send_form_to_es(received_on=first, xmlns='first', **kwargs_u2)

        self._send_form_to_es(received_on=second, xmlns='second', **kwargs_u3)
        self._send_form_to_es(received_on=third, xmlns='third', **kwargs_u3)
        self._send_form_to_es(received_on=first, xmlns='first', **kwargs_u3)

        result = get_last_form_submissions_by_user(self.domain, ['u1', 'u2', 'missing'])
        self.assertEqual(result['u1'][0]['xmlns'], 'third')
        self.assertEqual(result['u2'][0]['xmlns'], 'third')

        result = get_last_form_submissions_by_user(self.domain, ['u1'], '1234')
        self.assertEqual(result['u1'][0]['xmlns'], 'third')

        result = get_last_form_submissions_by_user(self.domain, ['u1', None], '1234')
        self.assertEqual(result['u1'][0]['xmlns'], 'third')
        self.assertEqual(result[None][0]['xmlns'], 'third')

    @run_with_all_backends
    def test_get_form_counts_by_user_xmlns(self):
        user1, user2 = 'u1', 'u2'
        app1, app2 = '123', '567'
        xmlns1, xmlns2 = 'abc', 'efg'

        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)

        received_on = datetime(2013, 7, 15, 0, 0, 0)
        received_on_out = datetime(2013, 6, 15, 0, 0, 0)
        self._send_form_to_es(received_on=received_on_out, completion_time=received_on, user_id=user1, app_id=app1, xmlns=xmlns1)
        self._send_form_to_es(received_on=received_on, user_id=user1, app_id=app1, xmlns=xmlns1)
        self._send_form_to_es(received_on=received_on, user_id=user1, app_id=app1, xmlns=xmlns1)
        self._send_form_to_es(received_on=received_on, user_id=user1, app_id=app2, xmlns=xmlns2)
        self._send_form_to_es(received_on=received_on, user_id=user2, app_id=app2, xmlns=xmlns2)
        self._send_form_to_es(received_on=received_on, user_id=None, app_id=app2, xmlns=xmlns2)

        counts = get_form_counts_by_user_xmlns(self.domain, start, end)
        self.assertEqual(counts, {
            (user1, app1, xmlns1): 2,
            (user1, app2, xmlns2): 1,
            (user2, app2, xmlns2): 1,
        })

        counts_user1 = get_form_counts_by_user_xmlns(self.domain, start, end, user_ids=[user1])
        self.assertEqual(counts_user1, {
            (user1, app1, xmlns1): 2,
            (user1, app2, xmlns2): 1,
        })

        counts_xmlns2 = get_form_counts_by_user_xmlns(self.domain, start, end, xmlnss=[xmlns2])
        self.assertEqual(counts_xmlns2, {
            (user1, app2, xmlns2): 1,
            (user2, app2, xmlns2): 1,
        })

        by_completion = get_form_counts_by_user_xmlns(self.domain, start, end, by_submission_time=False)
        self.assertEqual(by_completion, {
            (user1, app1, xmlns1): 1
        })

        counts_missing_user = get_form_counts_by_user_xmlns(self.domain, start, end, user_ids=[None])
        self.assertEqual(counts_missing_user, {
            (None, app2, xmlns2): 1,
        })

    @run_with_all_backends
    def test_get_form_duration_stats_by_user(self):
        """
        Tests the get_form_duration_stats_by_user basic ability to get duration stats
        grouped by user
        """
        user1, user2 = 'u1', 'u2'
        app1 = '123'
        xmlns1 = 'abc'

        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)

        time_start = datetime(2013, 6, 15, 0, 0, 0)
        completion_time = datetime(2013, 7, 15, 0, 0, 0)

        self._send_form_to_es(
            completion_time=completion_time,
            user_id=user1,
            app_id=app1,
            xmlns=xmlns1,
            time_start=time_start,
        )
        self._send_form_to_es(
            completion_time=completion_time,
            user_id=user2,
            app_id=app1,
            xmlns=xmlns1,
            time_start=time_start,
        )
        self._send_form_to_es(
            completion_time=completion_time,
            user_id=None,
            app_id=app1,
            xmlns=xmlns1,
            time_start=time_start,
        )

        results = get_form_duration_stats_by_user(
            self.domain,
            app1,
            xmlns1,
            [user1, user2, None],
            start,
            end,
            by_submission_time=False
        )

        self.assertEqual(results[user1]['count'], 1)
        self.assertEqual(timedelta(milliseconds=results[user1]['max']), completion_time - time_start)
        self.assertEqual(results[user2]['count'], 1)
        self.assertEqual(timedelta(milliseconds=results[user2]['max']), completion_time - time_start)
        self.assertEqual(results[MISSING_KEY]['count'], 1)
        self.assertEqual(timedelta(milliseconds=results[MISSING_KEY]['max']), completion_time - time_start)

    @run_with_all_backends
    def test_get_form_duration_stats_by_user_decoys(self):
        """
        Tests the get_form_duration_stats_by_user ability to filter out forms that
        do not fit within the filters specified
        """
        user1, user2 = 'u1', 'u2'
        app1, app2 = '123', '456'
        xmlns1, xmlns2 = 'abc', 'def'

        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)

        time_start = datetime(2013, 7, 2, 0, 0, 0)
        completion_time = datetime(2013, 7, 15, 0, 0, 0)
        received_on = datetime(2013, 7, 20, 0, 0, 0)
        received_on_late = datetime(2013, 7, 20, 0, 0, 0)

        self._send_form_to_es(
            completion_time=completion_time,
            user_id=user1,
            app_id=app1,
            xmlns=xmlns1,
            time_start=time_start,
            received_on=received_on,
        )

        # different app
        self._send_form_to_es(
            completion_time=completion_time,
            user_id=user1,
            app_id=app2,
            xmlns=xmlns1,
            time_start=time_start,
            received_on=received_on,
        )

        # different xmlns
        self._send_form_to_es(
            completion_time=completion_time,
            user_id=user1,
            app_id=app1,
            xmlns=xmlns2,
            time_start=time_start,
            received_on=received_on,
        )

        # out of time range
        self._send_form_to_es(
            completion_time=completion_time,
            user_id=user2,
            app_id=app1,
            xmlns=xmlns1,
            time_start=time_start,
            received_on=received_on_late,
        )

        results = get_form_duration_stats_by_user(
            self.domain,
            app1,
            xmlns1,
            [user1, user2],
            start,
            end,
            by_submission_time=True
        )

        self.assertEqual(results[user1]['count'], 1)
        self.assertEqual(timedelta(milliseconds=results[user1]['max']), completion_time - time_start)
        self.assertIsNone(results.get('user2'))

    @run_with_all_backends
    def test_get_form_duration_stats_for_users(self):
        """
        Tests the get_form_duration_stats_for_users basic ability to get duration stats
        """
        user1, user2 = 'u1', 'u2'
        app1 = '123'
        xmlns1 = 'abc'

        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)

        time_start = datetime(2013, 6, 15, 0, 0, 0)
        completion_time = datetime(2013, 7, 15, 0, 0, 0)

        self._send_form_to_es(
            completion_time=completion_time,
            user_id=user1,
            app_id=app1,
            xmlns=xmlns1,
            time_start=time_start,
        )
        self._send_form_to_es(
            completion_time=completion_time,
            user_id=user2,
            app_id=app1,
            xmlns=xmlns1,
            time_start=time_start,
        )
        self._send_form_to_es(
            completion_time=completion_time,
            user_id=None,
            app_id=app1,
            xmlns=xmlns1,
            time_start=time_start,
        )

        results = get_form_duration_stats_for_users(
            self.domain,
            app1,
            xmlns1,
            [user1, user2, None],
            start,
            end,
            by_submission_time=False
        )

        self.assertEqual(results['count'], 3)
        self.assertEqual(timedelta(milliseconds=results['max']), completion_time - time_start)

    @run_with_all_backends
    def test_get_form_duration_stats_for_users_decoys(self):
        """
        Tests the get_form_duration_stats_for_users ability to filter out forms that
        do not fit within the filters specified
        """
        user1, user2 = 'u1', 'u2'
        app1, app2 = '123', '456'
        xmlns1, xmlns2 = 'abc', 'def'

        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)

        time_start = datetime(2013, 7, 2, 0, 0, 0)
        completion_time = datetime(2013, 7, 15, 0, 0, 0)
        received_on = datetime(2013, 7, 20, 0, 0, 0)
        received_on_late = datetime(2013, 8, 20, 0, 0, 0)

        self._send_form_to_es(
            completion_time=completion_time,
            user_id=user1,
            app_id=app1,
            xmlns=xmlns1,
            time_start=time_start,
            received_on=received_on,
        )

        # different app
        self._send_form_to_es(
            completion_time=completion_time,
            user_id=user1,
            app_id=app2,
            xmlns=xmlns1,
            time_start=time_start,
            received_on=received_on,
        )

        # different xmlns
        self._send_form_to_es(
            completion_time=completion_time,
            user_id=user1,
            app_id=app1,
            xmlns=xmlns2,
            time_start=time_start,
            received_on=received_on,
        )

        # out of time range
        self._send_form_to_es(
            completion_time=completion_time,
            user_id=user2,
            app_id=app1,
            xmlns=xmlns1,
            time_start=time_start,
            received_on=received_on_late,
        )

        results = get_form_duration_stats_for_users(
            self.domain,
            app1,
            xmlns1,
            [user1, user2],
            start,
            end,
            by_submission_time=True
        )

        self.assertEqual(results['count'], 1)
        self.assertEqual(timedelta(milliseconds=results['max']), completion_time - time_start)

    @run_with_all_backends
    def test_get_all_user_ids_submitted_without_app_id(self):
        user1, user2 = 'u1', 'u2'
        app1, app2 = '123', '567'
        xmlns1, xmlns2 = 'abc', 'efg'

        received_on = datetime(2013, 7, 15, 0, 0, 0)

        self._send_form_to_es(received_on=received_on, user_id=user1, app_id=app1, xmlns=xmlns1)
        self._send_form_to_es(received_on=received_on, user_id=user2, app_id=app2, xmlns=xmlns2)

        user_ids = get_all_user_ids_submitted(self.domain)
        self.assertEqual(user_ids, ['u1', 'u2'])

    @run_with_all_backends
    def test_get_all_user_ids_submitted_with_app_id(self):
        user1, user2 = 'u1', 'u2'
        app1, app2 = '123', '567'
        xmlns1, xmlns2 = 'abc', 'efg'

        received_on = datetime(2013, 7, 15, 0, 0, 0)

        self._send_form_to_es(received_on=received_on, user_id=user1, app_id=app1, xmlns=xmlns1)
        self._send_form_to_es(received_on=received_on, user_id=user2, app_id=app2, xmlns=xmlns2)

        user_ids = get_all_user_ids_submitted(self.domain, app1)
        self.assertEqual(user_ids, ['u1'])
        user_ids = get_all_user_ids_submitted(self.domain, app2)
        self.assertEqual(user_ids, ['u2'])

    @run_with_all_backends
    def test_get_username_in_last_form_submitted(self):
        user1, user2 = 'u1', 'u2'
        app1 = '123'
        xmlns1 = 'abc'

        received_on = datetime(2013, 7, 15, 0, 0, 0)

        self._send_form_to_es(received_on=received_on, user_id=user1, app_id=app1, xmlns=xmlns1, username=user1)
        self._send_form_to_es(received_on=received_on, user_id=user2, app_id=app1, xmlns=xmlns1, username=user2)

        user_ids = get_username_in_last_form_user_id_submitted(self.domain, user1)
        self.assertEqual(user_ids, 'u1')
        user_ids = get_username_in_last_form_user_id_submitted(self.domain, user2)
        self.assertEqual(user_ids, 'u2')


class TestUserESAccessors(SimpleTestCase):

    def setUp(self):
        super(TestUserESAccessors, self).setUp()
        self.username = 'superman'
        self.first_name = 'clark'
        self.last_name = 'kent'
        self.doc_type = 'CommCareUser'
        self.domain = 'user-esaccessors-test'
        self.es = get_es_new()
        ensure_index_deleted(USER_INDEX)
        initialize_index_and_mapping(self.es, USER_INDEX_INFO)

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(USER_INDEX)
        super(TestUserESAccessors, cls).tearDownClass()

    def _send_user_to_es(self, _id=None, is_active=True):
        user = CommCareUser(
            domain=self.domain,
            username=self.username,
            _id=_id or uuid.uuid4().hex,
            is_active=is_active,
            first_name=self.first_name,
            last_name=self.last_name,
        )
        send_to_elasticsearch('users', user.to_json())
        self.es.indices.refresh(USER_INDEX)
        return user

    def test_active_user_query(self):
        self._send_user_to_es('123')
        results = get_user_stubs(['123'])

        self.assertEquals(len(results), 1)
        self.assertEquals(results[0], {
            '_id': '123',
            'username': self.username,
            'is_active': True,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'doc_type': self.doc_type,
            'location_id': None
        })

    def test_inactive_user_query(self):
        self._send_user_to_es('123', is_active=False)
        results = get_user_stubs(['123'])

        self.assertEquals(len(results), 1)
        self.assertEquals(results[0], {
            '_id': '123',
            'username': self.username,
            'is_active': False,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'doc_type': self.doc_type,
            'location_id': None
        })


class TestGroupESAccessors(SimpleTestCase):

    def setUp(self):
        self.group_name = 'justice league'
        self.domain = 'group-esaccessors-test'
        self.reporting = True
        self.case_sharing = False
        self.es = get_es_new()

    def _send_group_to_es(self, _id=None):
        group = Group(
            domain=self.domain,
            name=self.group_name,
            case_sharing=self.case_sharing,
            reporting=self.reporting,
            _id=_id or uuid.uuid4().hex,
        )
        send_to_elasticsearch('groups', group.to_json())
        self.es.indices.refresh(GROUP_INDEX_INFO.index)
        return group

    def test_group_query(self):
        self._send_group_to_es('123')
        results = get_group_stubs(['123'])

        self.assertEquals(len(results), 1)
        self.assertEquals(results[0], {
            '_id': '123',
            'name': self.group_name,
            'case_sharing': self.case_sharing,
            'reporting': self.reporting,
        })


class TestCaseESAccessors(BaseESAccessorsTest):

    es_index_info = CASE_INDEX_INFO

    def setUp(self):
        super(TestCaseESAccessors, self).setUp()
        self.owner_id = 'batman'
        self.user_id = 'robin'
        self.case_type = 'heroes'

    def _send_case_to_es(self,
            domain=None,
            owner_id=None,
            user_id=None,
            case_type=None,
            opened_on=None,
            closed_on=None):

        actions = [CommCareCaseAction(
            action_type=CASE_ACTION_CREATE,
            date=opened_on,
        )]

        case = CommCareCase(
            _id=uuid.uuid4().hex,
            domain=domain or self.domain,
            owner_id=owner_id or self.owner_id,
            user_id=user_id or self.user_id,
            type=case_type or self.case_type,
            opened_on=opened_on or datetime.now(),
            opened_by=user_id or self.user_id,
            closed_on=closed_on,
            closed_by=user_id or self.user_id,
            actions=actions,
        )
        send_to_elasticsearch('cases', case.to_json())
        self.es.indices.refresh(CASE_INDEX_INFO.index)
        return case

    def test_scroll_case_names(self):
        case_one = self._send_case_to_es()
        case_two = self._send_case_to_es()

        self.assertEqual(
            len(list(scroll_case_names(self.domain, [case_one.case_id, case_two.case_id]))),
            2
        )
        self.assertEqual(
            len(list(scroll_case_names('wrong-domain', [case_one.case_id, case_two.case_id]))),
            0
        )
        self.assertEqual(
            len(list(scroll_case_names(self.domain, [case_one.case_id]))),
            1
        )

    def test_get_active_case_counts(self):
        datespan = DateSpan(datetime(2013, 7, 1), datetime(2013, 7, 30))
        opened_on = datetime(2013, 7, 15)
        opened_on_not_active_range = datetime(2013, 6, 15)

        self._send_case_to_es(opened_on=opened_on)
        self._send_case_to_es(opened_on=opened_on_not_active_range)

        results = get_active_case_counts_by_owner(self.domain, datespan)
        self.assertEqual(results[self.owner_id], 1)

    def test_get_total_case_counts(self):
        datespan = DateSpan(datetime(2013, 7, 1), datetime(2013, 7, 30))
        opened_on = datetime(2013, 7, 15)
        opened_on_not_active_range = datetime(2013, 6, 15)

        self._send_case_to_es(opened_on=opened_on)
        self._send_case_to_es(opened_on=opened_on_not_active_range)
        self._send_case_to_es(opened_on=opened_on, case_type='commcare-user')

        results = get_total_case_counts_by_owner(self.domain, datespan)
        self.assertEqual(results[self.owner_id], 2)

    def test_get_active_case_counts_case_type(self):
        """Ensures that you can get cases by type"""
        datespan = DateSpan(datetime(2013, 7, 1), datetime(2013, 7, 30))
        opened_on = datetime(2013, 7, 15)

        self._send_case_to_es(opened_on=opened_on, case_type='villians')
        self._send_case_to_es(opened_on=opened_on, case_type=self.case_type)

        results = get_active_case_counts_by_owner(self.domain, datespan, [self.case_type])
        self.assertEqual(results[self.owner_id], 1)

    def test_get_active_case_counts_domain(self):
        """Ensure that cases only get grabbed if in the domain"""
        datespan = DateSpan(datetime(2013, 7, 1), datetime(2013, 7, 30))
        opened_on = datetime(2013, 7, 15)

        self._send_case_to_es(opened_on=opened_on, domain='villians')
        self._send_case_to_es(opened_on=opened_on, domain=self.domain)

        results = get_active_case_counts_by_owner(self.domain, datespan)
        self.assertEqual(results[self.owner_id], 1)

    def test_get_total_case_counts_closed(self):
        """Test a case closure before the startdate"""

        datespan = DateSpan(datetime(2013, 7, 1), datetime(2013, 7, 30))
        opened_on = datetime(2013, 7, 15)
        opened_on_early = datetime(2013, 6, 14)
        closed_on = datetime(2013, 6, 15)

        self._send_case_to_es(opened_on=opened_on)
        self._send_case_to_es(opened_on=opened_on_early, closed_on=closed_on)

        results = get_total_case_counts_by_owner(self.domain, datespan)
        self.assertEqual(results[self.owner_id], 1)

    def test_get_total_case_counts_opened_after(self):
        """Test a case opened after the startdate datespan"""

        datespan = DateSpan(datetime(2013, 7, 1), datetime(2013, 7, 30))
        opened_on = datetime(2013, 8, 15)

        self._send_case_to_es(opened_on=opened_on)

        results = get_total_case_counts_by_owner(self.domain, datespan)
        self.assertEqual(results, {})

    def test_get_case_counts_opened_by_user(self):
        datespan = DateSpan(datetime(2013, 7, 1), datetime(2013, 7, 30))
        opened_on = datetime(2013, 7, 15)

        self._send_case_to_es(opened_on=opened_on)
        self._send_case_to_es(opened_on=opened_on, case_type='commcare-user')

        results = get_case_counts_opened_by_user(self.domain, datespan)
        self.assertEqual(results[self.user_id], 1)

    def test_get_case_counts_closed_by_user(self):
        datespan = DateSpan(datetime(2013, 7, 1), datetime(2013, 7, 30))
        opened_on = datetime(2013, 7, 15)

        self._send_case_to_es(opened_on=opened_on)

        results = get_case_counts_closed_by_user(self.domain, datespan)
        self.assertEqual(results, {})

        self._send_case_to_es(opened_on=opened_on, closed_on=opened_on)

        results = get_case_counts_closed_by_user(self.domain, datespan)
        self.assertEqual(results[self.user_id], 1)

    def test_get_case_counts_opened_domain(self):
        datespan = DateSpan(datetime(2013, 7, 1), datetime(2013, 7, 30))
        opened_on = datetime(2013, 7, 15)

        self._send_case_to_es(opened_on=opened_on, domain='not here')

        results = get_case_counts_opened_by_user(self.domain, datespan)
        self.assertEqual(results, {})

    def test_get_case_counts_opened_case_type(self):
        datespan = DateSpan(datetime(2013, 7, 1), datetime(2013, 7, 30))
        opened_on = datetime(2013, 7, 15)

        self._send_case_to_es(opened_on=opened_on)

        results = get_case_counts_opened_by_user(self.domain, datespan, case_types=['not-here'])
        self.assertEqual(results, {})

    def test_get_case_types(self):
        self._send_case_to_es(case_type='t1')
        self._send_case_to_es(case_type='t2')
        self._send_case_to_es(case_type='t3', closed_on=datetime.utcnow())
        self._send_case_to_es(domain='other', case_type='t4')

        case_types = get_case_types_for_domain_es(self.domain)
        self.assertEqual(case_types, {'t1', 't2', 't3'})
        self.assertEqual({'t4'}, get_case_types_for_domain_es('other'))
        self.assertEqual(set(), get_case_types_for_domain_es('none'))

    def test_get_case_types_case_sensitive(self):
        self._send_case_to_es(case_type='child')
        self._send_case_to_es(case_type='Child')
        case_types = get_case_types_for_domain_es(self.domain)
        self.assertEqual(case_types, {'child', 'Child'})

    def test_get_case_types_caching(self):
        self._send_case_to_es(case_type='t1')

        self.assertEqual({'t1'}, get_case_types_for_domain_es(self.domain))

        self._send_case_to_es(case_type='t2')
        # cached response
        self.assertEqual({'t1'}, get_case_types_for_domain_es(self.domain))

        # simulate a save
        from casexml.apps.case.signals import case_post_save
        case_post_save.send(self, case=CommCareCase(domain=self.domain, type='t2'))

        self.assertEqual({'t1', 't2'}, get_case_types_for_domain_es(self.domain))


class TestLedgerESAccessors(BaseESAccessorsTest):
    es_index_info = LEDGER_INDEX_INFO
    domain = uuid.uuid4().hex

    def _send_ledger_to_es(self, section_id, case_id, entry_id, balance):
        ledger = {
            "_id": uuid.uuid4().hex,
            "domain": self.domain,
            "section_id": section_id,
            "case_id": case_id,
            "entry_id": entry_id,
            "balance": balance,
        }
        send_to_elasticsearch('ledgers', ledger)
        self.es.indices.refresh(self.es_index_info.index)
        return ledger

    def _check_result(self, expected, entry_ids=None):
        result = []
        for row in get_aggregated_ledger_values(self.domain, 'case', 'section', entry_ids):
            result.append(row._asdict())
        self.assertItemsEqual(result, expected)

    def test_one_ledger(self):
        self._send_ledger_to_es('section', 'case', 'entry_id', 1)
        self._check_result([
            {'entry_id': 'entry_id', 'balance': 1}
        ])

    def test_two_ledger(self):
        self._send_ledger_to_es('section', 'case', 'entry_id', 1)
        self._send_ledger_to_es('section', 'case', 'entry_id', 3)
        self._check_result([
            {'entry_id': 'entry_id', 'balance': 4}
        ])

    def test_multiple_entries(self):
        self._send_ledger_to_es('section', 'case', 'entry_id', 1)
        self._send_ledger_to_es('section', 'case', 'entry_id', 3)
        self._send_ledger_to_es('section', 'case', 'entry_id2', 3)
        self._check_result([
            {'entry_id': 'entry_id2', 'balance': 3},
            {'entry_id': 'entry_id', 'balance': 4},
        ])

    def test_filter_entries(self):
        self._send_ledger_to_es('section', 'case', 'entry_id', 1)
        self._send_ledger_to_es('section', 'case', 'entry_id', 3)
        self._send_ledger_to_es('section', 'case', 'entry_id2', 3)
        self._check_result([
            {'entry_id': 'entry_id', 'balance': 4},
        ], entry_ids=['entry_id'])


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestCaseESAccessorsSQL(TestCaseESAccessors):

    def _send_case_to_es(self,
            domain=None,
            owner_id=None,
            user_id=None,
            case_type=None,
            opened_on=None,
            closed_on=None):

        case = CommCareCaseSQL(
            case_id=uuid.uuid4().hex,
            domain=domain or self.domain,
            owner_id=owner_id or self.owner_id,
            modified_by=user_id or self.user_id,
            type=case_type or self.case_type,
            opened_on=opened_on or datetime.now(),
            opened_by=user_id or self.user_id,
            closed_on=closed_on,
            closed_by=user_id or self.user_id,
            server_modified_on=datetime.utcnow(),
            closed=bool(closed_on)
        )

        case.track_create(CaseTransaction(
            type=CaseTransaction.TYPE_FORM,
            form_id=uuid.uuid4().hex,
            case=case,
            server_date=opened_on,
        ))

        es_case = transform_case_for_elasticsearch(case.to_json())
        send_to_elasticsearch('cases', es_case)
        self.es.indices.refresh(CASE_INDEX)
        return case
