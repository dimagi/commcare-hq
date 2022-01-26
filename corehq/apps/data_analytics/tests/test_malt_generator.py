import datetime
from unittest.mock import Mock, patch

from django.http import Http404
from django.test import SimpleTestCase, TestCase

from dimagi.utils.dates import DateSpan
from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.app_manager.const import AMPLIFIES_YES, AMPLIFIES_NOT_SET
from corehq.apps.app_manager.models import Application
from corehq.apps.data_analytics.const import NOT_SET, YES
from corehq.apps.data_analytics.malt_generator import MALTTableGenerator, _get_malt_app_data, MaltAppData, \
    DEFAULT_MINIMUM_USE_THRESHOLD, DEFAULT_EXPERIENCED_THRESHOLD
from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.data_analytics.tests.utils import save_to_es_analytics_db
from corehq.apps.domain.models import Domain
from corehq.apps.es.tests.utils import es_test
from corehq.apps.smsforms.app import COMMCONNECT_DEVICE_ID
from corehq.apps.users.models import CommCareUser
from corehq.const import MISSING_APP_ID
from corehq.elastic import get_es_new
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import disable_quickcache


@es_test
class MaltGeneratorTest(TestCase):

    DOMAIN_NAME = "test"
    USERNAME = "malt-user"
    DEVICE_ID = "my_phone"
    UNKNOWN_ID = "UNKNOWN_ID"

    correct_date = datetime.datetime.now()
    out_of_range_date = correct_date - datetime.timedelta(days=32)
    malt_month = DateSpan.from_month(correct_date.month, correct_date.year)

    @classmethod
    def setUpClass(cls):
        super(MaltGeneratorTest, cls).setUpClass()
        cls.es = get_es_new()
        ensure_index_deleted(XFORM_INDEX_INFO.index)
        initialize_index_and_mapping(cls.es, XFORM_INDEX_INFO)
        cls._setup_domain_user()
        cls._setup_apps()
        cls._setup_forms()
        cls.es.indices.refresh(XFORM_INDEX_INFO.index)
        cls.run_malt_generation()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        MALTRow.objects.all().delete()
        ensure_index_deleted(XFORM_INDEX_INFO.index)
        super(MaltGeneratorTest, cls).tearDownClass()

    @classmethod
    def _setup_domain_user(cls):
        cls.domain = Domain(name=cls.DOMAIN_NAME)
        cls.domain.save()
        cls.user = CommCareUser.create(cls.DOMAIN_NAME, cls.USERNAME, '*****', None, None)
        cls.user.save()
        cls.user_id = cls.user._id

    @classmethod
    def _setup_apps(cls):
        cls.non_wam_app = Application.new_app(cls.DOMAIN_NAME, "app 1")
        cls.wam_app = Application.new_app(cls.DOMAIN_NAME, "app 2")
        cls.wam_app.amplifies_workers = AMPLIFIES_YES
        cls.non_wam_app.save()
        cls.wam_app.save()
        cls.non_wam_app_id = cls.non_wam_app._id
        cls.wam_app_id = cls.wam_app._id

    @classmethod
    def _setup_forms(cls):
        def _save_form_data(app_id, received_on=cls.correct_date, device_id=cls.DEVICE_ID):
            save_to_es_analytics_db(
                domain=cls.DOMAIN_NAME,
                received_on=received_on,
                device_id=device_id,
                user_id=cls.user_id,
                app_id=app_id,
            )

        def _save_multiple_forms(app_ids, received_on):
            for app_id in app_ids:
                _save_form_data(app_id, received_on=received_on)

        out_of_range_form_apps = [
            cls.non_wam_app_id,
            cls.wam_app_id,
        ]
        in_range_form_apps = [
            # should be included in MALT
            cls.non_wam_app_id,
            cls.non_wam_app_id,
            cls.non_wam_app_id,
            cls.wam_app_id,
            cls.wam_app_id,
            # should be included in MALT
            '',
        ]

        _save_multiple_forms(out_of_range_form_apps, cls.out_of_range_date)
        _save_multiple_forms(in_range_form_apps, cls.correct_date)

        # should be included in MALT
        _save_form_data(cls.non_wam_app_id, device_id=COMMCONNECT_DEVICE_ID)

    @classmethod
    def run_malt_generation(cls):
        generator = MALTTableGenerator([cls.malt_month])
        generator.build_table()

    def _assert_malt_row_exists(self, query_filters):
        rows = MALTRow.objects.filter(username=self.USERNAME, **query_filters)
        self.assertEqual(rows.count(), 1)

    def test_wam_yes_malt_counts(self):
        # 2 forms for WAM.YES app
        self._assert_malt_row_exists({
            'app_id': self.wam_app_id,
            'num_of_forms': 2,
            'wam': YES,
        })

    def test_wam_not_set_malt_counts(self):
        # 3 forms from self.DEVICE_ID for WAM not-set app
        self._assert_malt_row_exists({
            'app_id': self.non_wam_app_id,
            'num_of_forms': 3,
            'wam': NOT_SET,
            'device_id': self.DEVICE_ID,
        })

        # 1 form from COMMONCONNECT_DEVICE_ID for WAM not-set app
        self._assert_malt_row_exists({
            'app_id': self.non_wam_app_id,
            'num_of_forms': 1,
            'wam': NOT_SET,
            'device_id': COMMCONNECT_DEVICE_ID,
        })

    def test_missing_app_id_is_included(self):
        # apps with MISSING_APP_ID should be included in MALT
        self._assert_malt_row_exists({
            'app_id': MISSING_APP_ID,
            'num_of_forms': 1,
            'wam': NOT_SET,
        })


@disable_quickcache
class TestGetMaltAppData(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestGetMaltAppData, cls).setUpClass()
        cls.default_app_data = MaltAppData(
            AMPLIFIES_NOT_SET,
            AMPLIFIES_NOT_SET,
            DEFAULT_MINIMUM_USE_THRESHOLD,
            DEFAULT_EXPERIENCED_THRESHOLD,
            False
        )

    def test_returns_default_app_data_if_no_app_id(self):
        actual_app_data = _get_malt_app_data('domain', None)
        self.assertEqual(actual_app_data, self.default_app_data)

    def test_returns_default_app_data_if_get_app_raises_Http404(self):
        with patch('corehq.apps.data_analytics.malt_generator.get_app') as mock_getapp:
            mock_getapp.side_effect = Http404
            actual_app_data = _get_malt_app_data('domain', 'app_id')
        self.assertEqual(actual_app_data, self.default_app_data)

    def test_returns_expected_app_data(self):
        mock_app = Mock()
        mock_app.amplifies_workers = True
        mock_app.amplifies_project = False
        mock_app.minimum_use_threshold = 1
        mock_app.experienced_threshold = 10
        mock_app.is_deleted.return_value = False

        with patch('corehq.apps.data_analytics.malt_generator.get_app', return_value=mock_app):
            actual_app_data = _get_malt_app_data('domain', 'app_id')

        self.assertEqual(actual_app_data, MaltAppData(True, False, 1, 10, False))
