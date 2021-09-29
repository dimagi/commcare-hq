import uuid
from datetime import datetime, timedelta

from django.test import SimpleTestCase, TestCase

import pytz
from corehq.util.es.elasticsearch import ConnectionError
from mock import MagicMock, patch

from casexml.apps.case.models import CommCareCase
from corehq.apps.commtrack.tests.util import bootstrap_domain
from dimagi.utils.dates import DateSpan
from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
    PROFILE_SLUG,
)
from corehq.apps.domain.calculations import cases_in_last, inactive_cases_in_last
from corehq.apps.enterprise.tests.utils import create_enterprise_permissions
from corehq.apps.es import CaseES, UserES
from corehq.apps.es.aggregations import MISSING_KEY
from corehq.apps.es.tests.utils import es_test
from corehq.apps.groups.models import Group
from corehq.apps.hqcase.utils import SYSTEM_FORM_XMLNS, get_case_by_identifier
from corehq.apps.locations.tests.util import setup_locations_and_types, restrict_user_by_location
from corehq.apps.reports.analytics.esaccessors import (
    get_active_case_counts_by_owner,
    get_all_user_ids_submitted,
    get_case_counts_closed_by_user,
    get_case_counts_opened_by_user,
    get_case_types_for_domain_es,
    get_case_and_action_counts_for_domains,
    get_completed_counts_by_user,
    get_form_counts_by_user_xmlns,
    get_form_counts_for_domains,
    get_form_duration_stats_by_user,
    get_form_duration_stats_for_users,
    get_form_ids_having_multimedia,
    get_forms,
    get_last_submission_time_for_users,
    get_group_stubs,
    get_form_name_from_last_submission_for_xmlns,
    get_paged_forms_by_type,
    get_submission_counts_by_date,
    get_submission_counts_by_user,
    get_total_case_counts_by_owner,
    get_user_stubs,
    get_groups_by_querystring,
    get_username_in_last_form_user_id_submitted,
    guess_form_name_from_submissions_using_xmlns,
    scroll_case_names,
)
from corehq.apps.reports.standard.cases.utils import query_location_restricted_cases
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
from corehq.blobs.mixin import BlobMetaRef
from corehq.apps.domain.shortcuts import create_domain
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CaseTransaction, CommCareCaseSQL
from corehq.form_processor.utils import TestFormMetadata
from corehq.pillows.case import transform_case_for_elasticsearch
from corehq.pillows.mappings.case_mapping import CASE_INDEX, CASE_INDEX_INFO
from corehq.pillows.mappings.group_mapping import GROUP_INDEX_INFO
from corehq.pillows.mappings.user_mapping import USER_INDEX, USER_INDEX_INFO
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.pillows.user import transform_user_for_elasticsearch
from corehq.pillows.utils import MOBILE_USER_TYPE, WEB_USER_TYPE
from corehq.pillows.xform import transform_xform_for_elasticsearch
from corehq.util.elastic import ensure_index_deleted, reset_es_index
from corehq.util.test_utils import make_es_ready_form, trap_extra_setup


@es_test
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
                for name, meta in attachment_dict.items()}
            form_pair.json_form['external_blobs'] = attachment_dict

        es_form = transform_xform_for_elasticsearch(form_pair.json_form)
        send_to_elasticsearch('forms', es_form)
        self.es.indices.refresh(XFORM_INDEX_INFO.alias)
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

    def test_basic_completed_by_user(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)

        self._send_form_to_es(completion_time=datetime(2013, 7, 2))

        results = get_completed_counts_by_user(self.domain, DateSpan(start, end))
        self.assertEqual(results['cruella_deville'], 1)

    def test_get_last_submission_time_for_users(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)

        self._send_form_to_es(received_on=datetime(2013, 7, 2))

        results = get_last_submission_time_for_users(self.domain, ['cruella_deville'], DateSpan(start, end))
        self.assertEqual(results['cruella_deville'], datetime(2013, 7, 2).date())

    def test_get_form_counts_for_domains(self):
        self._send_form_to_es()
        self._send_form_to_es()
        self._send_form_to_es(domain='other')

        self.assertEqual(
            get_form_counts_for_domains([self.domain, 'other']),
            {self.domain: 2, 'other': 1}
        )

    def test_completed_out_of_range_by_user(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)

        self._send_form_to_es(completion_time=datetime(2013, 8, 2))
        self._send_form_to_es(completion_time=datetime(2013, 7, 2))

        results = get_completed_counts_by_user(self.domain, DateSpan(start, end))
        self.assertEqual(results['cruella_deville'], 1)

    def test_completed_different_domain_by_user(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)

        self._send_form_to_es(completion_time=datetime(2013, 7, 3), domain='not-in-my-backyard')
        self._send_form_to_es(completion_time=datetime(2013, 7, 2))

        results = get_completed_counts_by_user(self.domain, DateSpan(start, end))
        self.assertEqual(results['cruella_deville'], 1)

    def test_basic_submission_by_user(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)
        received_on = datetime(2013, 7, 15)

        self._send_form_to_es(received_on=received_on)

        results = get_submission_counts_by_user(self.domain, DateSpan(start, end))
        self.assertEqual(results['cruella_deville'], 1)

    def test_get_form_name_from_last_submission_for_xmlns(self):
        xmlns = 'http://a.b.org'
        kwargs = {
            'user_id': 'u1',
            'app_id': '1234',
            'domain': self.domain,
            'xmlns': xmlns
        }

        first = datetime(2013, 7, 15, 0, 0, 0)
        second = datetime(2013, 7, 16, 0, 0, 0)
        third = datetime(2013, 7, 17, 0, 0, 0)

        self._send_form_to_es(received_on=second, form_name='2', **kwargs)
        self._send_form_to_es(received_on=third, form_name='3', **kwargs)
        self._send_form_to_es(received_on=first, form_name='1', **kwargs)

        name = get_form_name_from_last_submission_for_xmlns(self.domain, xmlns)
        self.assertEqual(name, '3')

        name = get_form_name_from_last_submission_for_xmlns(self.domain, 'missing')
        self.assertIsNone(name)

    def test_guess_form_name_from_xmlns_not_found(self):
        self.assertEqual(None, guess_form_name_from_submissions_using_xmlns('missing', 'missing'))

    def test_guess_form_name_from_xmlns(self):
        form_name = 'my cool form'
        xmlns = 'http://a.b.org'
        self._send_form_to_es(
            xmlns=xmlns,
            form_name=form_name,
        )
        self.assertEqual(form_name, guess_form_name_from_submissions_using_xmlns(self.domain, xmlns))

    def test_submission_out_of_range_by_user(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)

        self._send_form_to_es(received_on=datetime(2013, 8, 15))

        self._send_form_to_es(received_on=datetime(2013, 7, 15))

        results = get_submission_counts_by_user(self.domain, DateSpan(start, end))
        self.assertEqual(results['cruella_deville'], 1)

    def test_submission_different_domain_by_user(self):
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)
        received_on = datetime(2013, 7, 15)

        self._send_form_to_es(received_on=received_on)
        self._send_form_to_es(received_on=received_on, domain='not-in-my-backyard')

        results = get_submission_counts_by_user(self.domain, DateSpan(start, end))
        self.assertEqual(results['cruella_deville'], 1)

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
        self.assertEqual(results['2013-07-15'], 1)

    def test_get_paged_forms_by_type(self):
        self._send_form_to_es()
        self._send_form_to_es()

        paged_result = get_paged_forms_by_type(self.domain, ['xforminstance'], size=1)
        self.assertEqual(len(paged_result.hits), 1)
        self.assertEqual(paged_result.total, 2)

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
        self.assertEqual(results['2013-07-14'], 1)

    def test_timezones_ahead_utc_in_get_submission_counts_by_date(self):
        """
        When bucketing form submissions, the returned bucket key needs to be converted to a datetime with
        the timezone specified. Specifically an issue for timezones ahead of UTC (positive offsets)
        """
        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)
        received_on = datetime(2013, 7, 15)

        self._send_form_to_es(received_on=received_on)
        self._send_form_to_es(received_on=received_on, xmlns=SYSTEM_FORM_XMLNS)

        results = get_submission_counts_by_date(
            self.domain,
            ['cruella_deville'],
            DateSpan(start, end),
            pytz.timezone('Africa/Johannesburg')
        )
        self.assertEqual(results['2013-07-15'], 1)

    def test_get_form_counts_by_user_xmlns(self):
        user1, user2 = 'u1', 'u2'
        app1, app2 = '123', '567'
        xmlns1, xmlns2 = 'abc', 'efg'

        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)

        received_on = datetime(2013, 7, 15, 0, 0, 0)
        received_on_out = datetime(2013, 6, 15, 0, 0, 0)
        self._send_form_to_es(received_on=received_on_out, completion_time=received_on,
                              user_id=user1, app_id=app1, xmlns=xmlns1)
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

    def test_xmlns_case_sensitivity_for_get_form_counts_by_user_xmlns(self):
        user = 'u1'
        app = '123'
        # the important part of this test is an xmlns identifier with both lower and uppercase characters
        xmlns = 'LmN'

        start = datetime(2013, 7, 1)
        end = datetime(2013, 7, 30)

        received_on = datetime(2013, 7, 15, 0, 0, 0)
        self._send_form_to_es(received_on=received_on, user_id=user, app_id=app, xmlns=xmlns)

        check_case_sensitivity = get_form_counts_by_user_xmlns(self.domain, start, end,
                                                               user_ids=[user], xmlnss=[xmlns])
        self.assertEqual(check_case_sensitivity, {
            (user, app, xmlns): 1,
        })

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

    def test_get_all_user_ids_submitted_without_app_id(self):
        user1, user2 = 'u1', 'u2'
        app1, app2 = '123', '567'
        xmlns1, xmlns2 = 'abc', 'efg'

        received_on = datetime(2013, 7, 15, 0, 0, 0)

        self._send_form_to_es(received_on=received_on, user_id=user1, app_id=app1, xmlns=xmlns1)
        self._send_form_to_es(received_on=received_on, user_id=user2, app_id=app2, xmlns=xmlns2)

        user_ids = get_all_user_ids_submitted(self.domain)
        self.assertEqual(user_ids, ['u1', 'u2'])

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


@es_test
class TestUserESAccessors(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'user-esaccessors-test'
        cls.domain_obj = create_domain(cls.domain)

        cls.source_domain = cls.domain + "-source"
        cls.source_domain_obj = create_domain(cls.source_domain)
        create_enterprise_permissions("a@a.com", cls.source_domain, [cls.domain])

        cls.definition = CustomDataFieldsDefinition(domain=cls.domain,
                                                    field_type=UserFieldsView.field_type)
        cls.definition.save()
        cls.definition.set_fields([
            Field(slug='job', label='Job'),
        ])
        cls.definition.save()
        cls.profile = CustomDataFieldsProfile(
            name='daily_planet_staff',
            fields={'job': 'reporter'},
            definition=cls.definition,
        )
        cls.profile.save()

        cls.user = CommCareUser.create(
            cls.domain,
            'superman',
            'secret agent man',
            None,
            None,
            first_name='clark',
            last_name='kent',
            is_active=True,
            metadata={PROFILE_SLUG: cls.profile.id, 'office': 'phone_booth'},
        )
        cls.user.save()

    def setUp(self):
        super(TestUserESAccessors, self).setUp()
        self.es = get_es_new()
        ensure_index_deleted(USER_INDEX)
        initialize_index_and_mapping(self.es, USER_INDEX_INFO)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        cls.source_domain_obj.delete()
        cls.definition.delete()
        ensure_index_deleted(USER_INDEX)
        super(TestUserESAccessors, cls).tearDownClass()

    def _send_user_to_es(self, is_active=True):
        self.user.is_active = is_active
        send_to_elasticsearch('users', transform_user_for_elasticsearch(self.user.to_json()))
        self.es.indices.refresh(USER_INDEX)

    def test_active_user_query(self):
        self._send_user_to_es()
        results = get_user_stubs([self.user._id], ['user_data_es'])

        self.assertEqual(len(results), 1)
        metadata = results[0].pop('user_data_es')
        self.assertEqual({
            'commcare_project': 'user-esaccessors-test',
            PROFILE_SLUG: self.profile.id,
            'job': 'reporter',
            'office': 'phone_booth',
        }, {item['key']: item['value'] for item in metadata})

        self.assertEqual(results[0], {
            '_id': self.user._id,
            '__group_ids': [],
            'username': self.user.username,
            'is_active': True,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'doc_type': 'CommCareUser',
            'location_id': None,
        })

    def test_inactive_user_query(self):
        self._send_user_to_es(is_active=False)
        results = get_user_stubs([self.user._id])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], {
            '_id': self.user._id,
            '__group_ids': [],
            'username': self.user.username,
            'is_active': False,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'doc_type': 'CommCareUser',
            'location_id': None
        })

    def test_domain_allow_enterprise(self):
        self._send_user_to_es()
        self.assertEqual(['superman'], UserES().domain(self.domain).values_list('username', flat=True))
        self.assertEqual([], UserES().domain(self.source_domain).values_list('username', flat=True))
        self.assertEqual(
            ['superman'],
            UserES().domain(self.domain, allow_enterprise=True).values_list('username', flat=True)
        )


@es_test
class TestGroupESAccessors(SimpleTestCase):

    def setUp(self):
        self.domain = 'group-esaccessors-test'
        self.reporting = True
        self.es = get_es_new()
        reset_es_index(GROUP_INDEX_INFO)

    def _send_group_to_es(self, name, _id=None, case_sharing=False):
        group = Group(
            domain=self.domain,
            name=name,
            case_sharing=case_sharing,
            reporting=self.reporting,
            _id=_id or uuid.uuid4().hex,
        )
        send_to_elasticsearch('groups', group.to_json())
        self.es.indices.refresh(GROUP_INDEX_INFO.index)
        return group

    def test_group_query(self):
        name = 'justice-league'
        self._send_group_to_es(name, '123')
        results = get_group_stubs(['123'])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], {
            '_id': '123',
            'name': name,
            'case_sharing': False,
            'reporting': self.reporting,
        })

    def test_group_search_query(self):
        self._send_group_to_es('Milkyway', '1')
        self._send_group_to_es('Freeroad', '2')
        self._send_group_to_es('Freeway', '3', True)
        self.assertEqual(
            get_groups_by_querystring(self.domain, 'Free', False),
            [
                {'id': '2', 'text': 'Freeroad'},
                {'id': '3', 'text': 'Freeway'},
            ]
        )
        self.assertEqual(
            get_groups_by_querystring(self.domain, 'way', True),
            [
                {'id': '3', 'text': 'Freeway'},
            ]
        )


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
            closed_on=None,
            modified_on=None):

        case = CommCareCaseSQL(
            case_id=uuid.uuid4().hex,
            domain=domain or self.domain,
            owner_id=owner_id or self.owner_id,
            modified_by=user_id or self.user_id,
            type=case_type or self.case_type,
            opened_on=opened_on or datetime.now(),
            opened_by=user_id or self.user_id,
            closed_on=closed_on,
            modified_on=modified_on or datetime.now(),
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

    def test_get_case_and_action_counts_for_domains(self):
        self._send_case_to_es()
        self._send_case_to_es()
        self._send_case_to_es('other')
        results = get_case_and_action_counts_for_domains([self.domain, 'other'])
        self.assertEqual(
            results,
            {
                self.domain: {'cases': 2, 'case_actions': 2},
                'other': {'cases': 1, 'case_actions': 1}
            }
        )

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

    def test_get_case_counts_in_last(self):
        self._send_case_to_es(modified_on=datetime.now() - timedelta(days=2))
        self._send_case_to_es(modified_on=datetime.now() - timedelta(days=2), case_type='new')
        self._send_case_to_es(modified_on=datetime.now() - timedelta(days=5), case_type='new')
        self.assertEqual(
            cases_in_last(self.domain, 3),
            2
        )
        self.assertEqual(
            cases_in_last(self.domain, 3, self.case_type),
            1
        )
        self.assertEqual(
            inactive_cases_in_last(self.domain, 6),
            0
        )
        self.assertEqual(
            inactive_cases_in_last(self.domain, 1),
            3
        )

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

    def test_case_by_identifier(self):
        self._send_case_to_es(case_type='ccuser')
        case = self._send_case_to_es()
        case.external_id = '123'
        case.save()
        case = CaseAccessors(self.domain).get_case(case.case_id)
        case_json = case.to_json()
        case_json['contact_phone_number'] = '234'
        es_case = transform_case_for_elasticsearch(case_json)
        send_to_elasticsearch('cases', es_case)
        self.es.indices.refresh(CASE_INDEX)
        self.assertEqual(
            get_case_by_identifier(self.domain, case.case_id).case_id,
            case.case_id
        )
        self.assertEqual(
            get_case_by_identifier(self.domain, '234').case_id,
            case.case_id
        )
        self.assertEqual(
            get_case_by_identifier(self.domain, '123').case_id,
            case.case_id
        )

    def test_location_restricted_cases(self):
        domain_obj = bootstrap_domain(self.domain)
        self.addCleanup(domain_obj.delete)

        location_type_names = ['state', 'county', 'city']
        location_structure = [
            ('Massachusetts', [
                ('Middlesex', [
                    ('Cambridge', []),
                    ('Somerville', []),
                ]),
                ('Suffolk', [
                    ('Boston', []),
                ])
            ])
        ]
        locations = setup_locations_and_types(self.domain, location_type_names, [], location_structure)[1]
        middlesex_user = CommCareUser.create(self.domain, 'guy-from-middlesex', '***', None, None)

        middlesex_user.add_to_assigned_locations(locations['Middlesex'])
        restrict_user_by_location(self.domain, middlesex_user)

        fake_request = MagicMock()
        fake_request.domain = self.domain
        fake_request.couch_user = middlesex_user

        self._send_case_to_es(owner_id=locations['Boston'].get_id)
        middlesex_case = self._send_case_to_es(owner_id=locations['Middlesex'].get_id)
        cambridge_case = self._send_case_to_es(owner_id=locations['Cambridge'].get_id)

        returned_case_ids = query_location_restricted_cases(
            CaseES().domain(self.domain),
            fake_request).get_ids()
        self.assertItemsEqual(returned_case_ids, [middlesex_case.case_id, cambridge_case.case_id])
