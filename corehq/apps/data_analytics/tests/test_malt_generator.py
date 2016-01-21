import datetime
from django.test import TestCase

from corehq.apps.app_manager.const import APP_V2, AMPLIFIES_YES
from corehq.apps.app_manager.models import Application
from corehq.apps.data_analytics.malt_generator import MALTTableGenerator
from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser
from corehq.apps.smsforms.app import COMMCONNECT_DEVICE_ID
from corehq.apps.sofabed.models import FormData, MISSING_APP_ID

from dimagi.utils.dates import DateSpan


class MaltGeneratorTest(TestCase):
    dependent_apps = [
        'corehq.apps.tzmigration', 'django_digest', 'auditcare', 'corehq.apps.users',
        'corehq.couchapps', 'corehq.apps.sofabed', 'corehq.apps.domain',
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
        cls._setup_domain_user()
        cls._setup_apps()
        cls._setup_sofabed_forms()
        cls.run_malt_generation()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        FormData.objects.all().delete()
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
        cls.app = Application.new_app(cls.DOMAIN_NAME, "app 1", APP_V2)
        cls.wam_app = Application.new_app(cls.DOMAIN_NAME, "app 2", APP_V2)
        cls.wam_app.amplifies_workers = AMPLIFIES_YES
        cls.app.save()
        cls.wam_app.save()
        cls.app_id = cls.app._id
        cls.wam_app_id = cls.wam_app._id

    @classmethod
    def _setup_sofabed_forms(cls):
        form_data_rows = []
        common_args = {  # values don't matter
            'time_start': cls.correct_date,
            'time_end': cls.correct_date,
            'duration': 10,
        }

        def _form_data(instance_id,
                       app_id,
                       received_on=cls.correct_date,
                       device_id=cls.DEVICE_ID):
            return FormData(
                domain=cls.DOMAIN_NAME,
                received_on=received_on,
                instance_id=instance_id,
                device_id=device_id,
                user_id=cls.user_id,
                app_id=app_id,
                **common_args
            )

        def _append_forms(forms, received_on):
            for form in forms:
                instance_id, app_id = form
                form_data_rows.append(
                    _form_data(instance_id, app_id, received_on=received_on)
                )

        out_of_range_forms = [
            ("out_of_range_1", cls.app_id),
            ("out_of_range_2", cls.wam_app_id),
        ]
        in_range_forms = [
            # should be included in MALT
            ('app_form1', cls.app_id),
            ('app_form2', cls.app_id),
            ('app_form3', cls.app_id),
            ('wam_app_form1', cls.wam_app_id),
            ('wam_app_form2', cls.wam_app_id),
            ('missing_app_form', MISSING_APP_ID),
        ]

        _append_forms(out_of_range_forms, cls.out_of_range_date)
        _append_forms(in_range_forms, cls.correct_date)

        sms_form = _form_data('sms_form', cls.app_id, device_id=COMMCONNECT_DEVICE_ID)
        form_data_rows.append(sms_form)

        FormData.objects.bulk_create(form_data_rows)

    @classmethod
    def run_malt_generation(cls):
        generator = MALTTableGenerator([cls.malt_month])
        generator.build_table()

    def _check_malt_rows(self, app_id, num_forms=None, wam_value=None, malt_row_count=1):
        app_rows = MALTRow.objects.filter(
            username=self.USERNAME,
            app_id=app_id,
        )
        self.assertEqual(app_rows.count(), malt_row_count)  # 1 row per app
        row = app_rows.all()[0]
        self.assertEqual(int(row.num_of_forms), num_forms)
        self.assertEqual(row.wam, wam_value)

    def test_two_wam_yes_apps(self):
        self._check_malt_rows(self.wam_app_id, 2, MALTRow.YES)

    def test_three_wam_not_set_apps(self):
        self._check_malt_rows(self.app_id, 3, MALTRow.NOT_SET)

    def test_missing_app_id_is_included(self):
        self._check_malt_rows(MISSING_APP_ID, 1, MALTRow.NOT_SET)
