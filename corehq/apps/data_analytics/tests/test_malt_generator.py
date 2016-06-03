import datetime
from django.test import TestCase

from corehq.apps.app_manager.const import APP_V2, AMPLIFIES_YES
from corehq.apps.app_manager.models import Application
from corehq.apps.data_analytics.malt_generator import MALTTableGenerator
from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.data_analytics.tests.utils import save_to_es_analytics_db
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser
from corehq.apps.smsforms.app import COMMCONNECT_DEVICE_ID
from corehq.const import MISSING_APP_ID
from corehq.pillows.xform import XFormPillow
from corehq.util.elastic import ensure_index_deleted

from dimagi.utils.dates import DateSpan
from pillowtop.es_utils import completely_initialize_pillow_index


class MaltGeneratorTest(TestCase):
    dependent_apps = [
        'corehq.apps.tzmigration', 'django_digest', 'auditcare', 'corehq.apps.users',
        'corehq.couchapps', 'corehq.apps.domain',
        'corehq.apps.app_manager',
    ]

    DOMAIN_NAME = "test"
    USERNAME = "malt-user"
    DEVICE_ID = "my_phone"
    UNKNOWN_ID = "UNKNOWN_ID"

    correct_date = datetime.datetime.now()
    out_of_range_date = correct_date - datetime.timedelta(days=32)
    malt_month = DateSpan.from_month(correct_date.month, correct_date.year)

    @classmethod
    def setUpClass(cls):
        cls.pillow = pillow = XFormPillow()
        ensure_index_deleted(pillow.es_index)
        completely_initialize_pillow_index(pillow)
        cls._setup_domain_user()
        cls._setup_apps()
        cls._setup_forms()
        pillow.get_es_new().indices.refresh(pillow.es_index)
        cls.run_malt_generation()

    def setUp(self):
        ensure_index_deleted(self.pillow.es_index)
        completely_initialize_pillow_index(self.pillow)

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        MALTRow.objects.all().delete()

    @classmethod
    def _setup_domain_user(cls):
        cls.domain = Domain(name=cls.DOMAIN_NAME)
        cls.domain.save()
        cls.user = CommCareUser.create(cls.DOMAIN_NAME, cls.USERNAME, '*****')
        cls.user.save()
        cls.user_id = cls.user._id

    @classmethod
    def _setup_apps(cls):
        cls.non_wam_app = Application.new_app(cls.DOMAIN_NAME, "app 1", APP_V2)
        cls.wam_app = Application.new_app(cls.DOMAIN_NAME, "app 2", APP_V2)
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
            'wam': MALTRow.YES,
        })

    def test_wam_not_set_malt_counts(self):
        # 3 forms from self.DEVICE_ID for WAM not-set app
        self._assert_malt_row_exists({
            'app_id': self.non_wam_app_id,
            'num_of_forms': 3,
            'wam': MALTRow.NOT_SET,
            'device_id': self.DEVICE_ID,
        })

        # 1 form from COMMONCONNECT_DEVICE_ID for WAM not-set app
        self._assert_malt_row_exists({
            'app_id': self.non_wam_app_id,
            'num_of_forms': 1,
            'wam': MALTRow.NOT_SET,
            'device_id': COMMCONNECT_DEVICE_ID,
        })

    def test_missing_app_id_is_included(self):
        # apps with MISSING_APP_ID should be included in MALT
        self._assert_malt_row_exists({
            'app_id': MISSING_APP_ID,
            'num_of_forms': 1,
            'wam': MALTRow.NOT_SET,
        })
