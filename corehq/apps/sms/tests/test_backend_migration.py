from corehq.apps.sms.mixin import MobileBackend, SMSLoadBalancingMixin, BackendMapping
from corehq.apps.sms.models import SQLMobileBackend, MobileBackendInvitation, SQLMobileBackendMapping
from corehq.messaging.ivrbackends.kookoo.models import KooKooBackend, SQLKooKooBackend
from corehq.messaging.smsbackends.apposit.models import AppositBackend, SQLAppositBackend
from corehq.messaging.smsbackends.grapevine.models import GrapevineBackend, SQLGrapevineBackend
from corehq.messaging.smsbackends.http.models import HttpBackend, SQLHttpBackend
from corehq.messaging.smsbackends.mach.models import MachBackend, SQLMachBackend
from corehq.messaging.smsbackends.megamobile.models import MegamobileBackend, SQLMegamobileBackend
from corehq.messaging.smsbackends.sislog.models import SQLSislogBackend
from corehq.messaging.smsbackends.smsgh.models import SMSGHBackend, SQLSMSGHBackend
from corehq.messaging.smsbackends.telerivet.models import TelerivetBackend, SQLTelerivetBackend
from corehq.messaging.smsbackends.test.models import TestSMSBackend, SQLTestSMSBackend
from corehq.messaging.smsbackends.tropo.models import TropoBackend, SQLTropoBackend
from corehq.messaging.smsbackends.twilio.models import TwilioBackend, SQLTwilioBackend
from corehq.messaging.smsbackends.unicel.models import UnicelBackend, SQLUnicelBackend
from corehq.messaging.smsbackends.yo.models import SQLYoBackend
from django.test import TestCase


class BackendMigrationTestCase(TestCase):
    def setUp(self):
        self._delete_all_backends()

    def tearDown(self):
        self._delete_all_backends()

    def _get_all_couch_backends(self):
        result = MobileBackend.view(
            'sms/global_backends',
            include_docs=True,
            reduce=False
        ).all()
        result.extend(
            MobileBackend.view(
                'sms/backend_by_owner_domain',
                include_docs=True,
                reduce=False
            ).all()
        )
        kookoo_backends = MobileBackend.view(
            'all_docs/by_doc_type',
            startkey=['KooKooBackend'],
            endkey=['KooKooBackend', {}],
            include_docs=True,
            reduce=False
        ).all()
        for backend in kookoo_backends:
            if not backend.base_doc.endswith('-Deleted'):
                result.append(backend)
        return result

    def _get_all_couch_backend_mappings(self):
        return BackendMapping.view('sms/backend_map', include_docs=True).all()

    def _count_all_sql_backends(self):
        return SQLMobileBackend.objects.count()

    def _count_all_sql_backend_invitations(self):
        return MobileBackendInvitation.objects.count()

    def _count_all_sql_backend_mappings(self):
        return SQLMobileBackendMapping.objects.count()

    def _create_or_update_couch_backend(
        self, cls, domain, name, display_name, incoming_api_id, authorized_domains,
        is_global, description, supported_countries, reply_to_phone_number,
        couch_obj=None, load_balancing_numbers=None, extra_fields=None
    ):
        couch_obj = couch_obj or cls()
        couch_obj.domain = domain
        couch_obj.name = name
        couch_obj.display_name = display_name
        couch_obj.incoming_api_id = incoming_api_id
        couch_obj.authorized_domains = authorized_domains
        couch_obj.is_global = is_global
        couch_obj.description = description
        couch_obj.supported_countries = supported_countries
        couch_obj.reply_to_phone_number = reply_to_phone_number

        if extra_fields:
            for k, v in extra_fields.iteritems():
                setattr(couch_obj, k, v)

        if load_balancing_numbers:
            couch_obj.x_phone_numbers = load_balancing_numbers

        couch_obj.save()
        return couch_obj

    def _create_or_update_sql_backend(
        self, cls, backend_type, hq_api_id, is_global, domain, name,
        display_name, description, supported_countries, extra_fields,
        reply_to_phone_number, load_balancing_numbers=None, shared_domains=None,
        sql_obj=None, couch_class=None
    ):
        sql_obj = sql_obj or cls()
        sql_obj.backend_type = backend_type
        sql_obj.hq_api_id = hq_api_id
        sql_obj.is_global = is_global
        sql_obj.domain = domain
        sql_obj.name = name
        sql_obj.display_name = display_name
        sql_obj.description = description
        sql_obj.supported_countries = supported_countries
        sql_obj.set_extra_fields(**extra_fields)
        sql_obj.reply_to_phone_number = reply_to_phone_number

        if load_balancing_numbers:
            sql_obj.load_balancing_numbers = load_balancing_numbers

        sql_obj.save()

        shared_domains = shared_domains or []
        if shared_domains:
            sql_obj.set_shared_domains(shared_domains)

        saved_domains = [i.domain for i in sql_obj.mobilebackendinvitation_set.all()]
        self.assertEqual(len(shared_domains), len(saved_domains))
        self.assertEqual(set(shared_domains), set(saved_domains))
        self.assertEqual(sql_obj.get_extra_fields(), extra_fields)

        return sql_obj

    def _compare_couch_backend(self, couch_obj, sql_obj, expected_doc_type):
        self.assertEqual(couch_obj.base_doc, 'MobileBackend')
        self.assertEqual(couch_obj.doc_type, expected_doc_type)
        self.assertEqual(couch_obj.domain, sql_obj.domain)
        self.assertEqual(couch_obj.name, sql_obj.name)
        self.assertEqual(couch_obj.display_name, sql_obj.display_name)

        shared_domains = [i.domain for i in sql_obj.mobilebackendinvitation_set.all()]
        self.assertEqual(len(couch_obj.authorized_domains), len(shared_domains))
        self.assertEqual(set(couch_obj.authorized_domains), set(shared_domains))

        self.assertEqual(couch_obj.is_global, sql_obj.is_global)
        self.assertEqual(couch_obj.description, sql_obj.description)
        self.assertEqual(couch_obj.supported_countries, sql_obj.supported_countries)
        self.assertEqual(couch_obj.reply_to_phone_number, sql_obj.reply_to_phone_number)
        self.assertEqual(couch_obj.backend_type, sql_obj.backend_type)

        for k, v in sql_obj.get_extra_fields().iteritems():
            self.assertEqual(getattr(couch_obj, k), v)

        if sql_obj.load_balancing_numbers:
            self.assertEqual(couch_obj.x_phone_numbers, sql_obj.load_balancing_numbers)

    def _compare_sql_backend(self, couch_obj, sql_obj, extra_fields):
        self.assertEqual(sql_obj.backend_type, couch_obj.backend_type)
        self.assertEqual(sql_obj.hq_api_id, couch_obj.incoming_api_id or couch_obj.get_api_id())
        self.assertEqual(sql_obj.is_global, couch_obj.is_global)
        self.assertEqual(sql_obj.domain, couch_obj.domain)
        self.assertEqual(sql_obj.name, couch_obj.name)
        self.assertEqual(sql_obj.display_name, couch_obj.display_name)
        self.assertEqual(sql_obj.description, couch_obj.description)
        self.assertEqual(sql_obj.supported_countries, couch_obj.supported_countries)
        self.assertEqual(sql_obj.extra_fields, extra_fields)
        self.assertEqual(sql_obj.deleted, False)
        self.assertEqual(sql_obj.reply_to_phone_number, couch_obj.reply_to_phone_number)
        if isinstance(couch_obj, SMSLoadBalancingMixin):
            self.assertEqual(sql_obj.load_balancing_numbers, couch_obj.phone_numbers)
        else:
            self.assertEqual(sql_obj.load_balancing_numbers, [])

        shared_domains = []
        for invitation in sql_obj.mobilebackendinvitation_set.all():
            self.assertTrue(invitation.accepted)
            shared_domains.append(invitation.domain)

        self.assertEqual(len(shared_domains), len(couch_obj.authorized_domains))
        self.assertEqual(set(shared_domains), set(couch_obj.authorized_domains))

    def _test_couch_backend_create(self, *args, **kwargs):
        couch_obj = self._create_or_update_couch_backend(*args, **kwargs)

        self.assertEqual(len(self._get_all_couch_backends()), 1)
        self.assertEqual(self._count_all_sql_backends(), 1)
        self.assertEqual(self._count_all_sql_backend_invitations(), len(couch_obj.authorized_domains))

        sql_obj = SQLMobileBackend.objects.get(couch_id=couch_obj._id)
        self._compare_sql_backend(couch_obj, sql_obj, kwargs.get('extra_fields', {}))

        return couch_obj

    def _test_couch_backend_update(self, *args, **kwargs):
        couch_obj = kwargs.get('couch_obj')
        self._create_or_update_couch_backend(*args, **kwargs)

        self.assertEqual(len(self._get_all_couch_backends()), 1)
        self.assertEqual(self._count_all_sql_backends(), 1)
        self.assertEqual(self._count_all_sql_backend_invitations(), len(couch_obj.authorized_domains))

        sql_obj = SQLMobileBackend.objects.get(couch_id=couch_obj._id)
        self._compare_sql_backend(couch_obj, sql_obj, kwargs.get('extra_fields', {}))

    def _test_couch_backend_retire(self, couch_obj):
        couch_obj.retire()

        self.assertEqual(len(self._get_all_couch_backends()), 0)
        self.assertEqual(self._count_all_sql_backends(), 1)
        self.assertEqual(self._count_all_sql_backend_invitations(), 0)

        self.assertTrue(couch_obj.base_doc.endswith('-Deleted'))
        sql_obj = SQLMobileBackend.objects.get(couch_id=couch_obj._id)
        self.assertTrue(sql_obj.deleted)

    def _test_sql_backend_create(self, *args, **kwargs):
        sql_obj = self._create_or_update_sql_backend(*args, **kwargs)

        self.assertEqual(len(self._get_all_couch_backends()), 1)
        self.assertEqual(self._count_all_sql_backends(), 1)

        couch_class = kwargs.get('couch_class')
        couch_obj = couch_class.get(sql_obj.couch_id)
        self._compare_couch_backend(couch_obj, sql_obj, couch_class.__name__)

        return sql_obj

    def _test_sql_backend_update(self, *args, **kwargs):
        sql_obj = kwargs.get('sql_obj')
        self._create_or_update_sql_backend(*args, **kwargs)

        self.assertEqual(len(self._get_all_couch_backends()), 1)
        self.assertEqual(self._count_all_sql_backends(), 1)

        couch_class = kwargs.get('couch_class')
        couch_obj = couch_class.get(sql_obj.couch_id)
        self._compare_couch_backend(couch_obj, sql_obj, couch_class.__name__)

    def _test_sql_backend_retire(self, sql_obj):
        sql_obj.soft_delete()

        self.assertEqual(len(self._get_all_couch_backends()), 0)
        self.assertEqual(self._count_all_sql_backends(), 1)
        self.assertEqual(self._count_all_sql_backend_invitations(), 0)

        self.assertTrue(sql_obj.deleted)
        couch_obj = MobileBackend.get(sql_obj.couch_id)
        self.assertTrue(couch_obj.base_doc.endswith('-Deleted'))

    def test_apposit_sql_to_couch(self):
        sql_obj = self._test_sql_backend_create(
            SQLAppositBackend,
            'SMS',
            'APPOSIT',
            True,
            None,
            'MOBILE_BACKEND_APPOSIT',
            "Apposit",
            "Apposit Description",
            ['251'],
            {
                'from_number': '1234',
                'username': 'user',
                'password': 'pass',
                'service_id': 'sid',
            },
            'xxxx',
            couch_class=AppositBackend
        )

        self._test_sql_backend_update(
            SQLAppositBackend,
            'SMS',
            'APPOSIT',
            True,
            None,
            'MOBILE_BACKEND_APPOSIT2',
            "Apposit2",
            "Apposit Description2",
            ['2519'],
            {
                'from_number': '12345',
                'username': 'user2',
                'password': 'pass2',
                'service_id': 'sid2',
            },
            'xxxxx',
            sql_obj=sql_obj,
            couch_class=AppositBackend
        )

        self._test_sql_backend_retire(sql_obj)

    def test_apposit_couch_to_sql(self):
        couch_obj = self._test_couch_backend_create(
            AppositBackend,
            None,
            'MOBILE_BACKEND_APPOSIT',
            "Apposit",
            None,
            [],
            True,
            "Apposit Description",
            ['251'],
            'xxxx',
            extra_fields={
                'from_number': '1234',
                'username': 'user',
                'password': 'pass',
                'service_id': 'sid',
            }
        )

        self._test_couch_backend_update(
            AppositBackend,
            None,
            'MOBILE_BACKEND_APPOSIT2',
            "Apposit2",
            None,
            [],
            True,
            "Apposit Description2",
            ['2519'],
            'xxxxx',
            couch_obj=couch_obj,
            extra_fields={
                'from_number': '12345',
                'username': 'user2',
                'password': 'pass2',
                'service_id': 'sid2',
            }
        )

        self._test_couch_backend_retire(couch_obj)

    def test_grapevine_sql_to_couch(self):
        sql_obj = self._test_sql_backend_create(
            SQLGrapevineBackend,
            'SMS',
            'GVI',
            True,
            None,
            'MOBILE_BACKEND_GRAPEVINE',
            "Grapevine",
            "Grapevine Description",
            ['27'],
            {
                'affiliate_code': 'abc',
                'authentication_code': 'def',
            },
            'xxxx',
            couch_class=GrapevineBackend
        )

        self._test_sql_backend_update(
            SQLGrapevineBackend,
            'SMS',
            'GVI',
            True,
            None,
            'MOBILE_BACKEND_GRAPEVINE2',
            "Grapevine2",
            "Grapevine Description2",
            ['27', '266'],
            {
                'affiliate_code': 'abc2',
                'authentication_code': 'def2',
            },
            'xxxxx',
            sql_obj=sql_obj,
            couch_class=GrapevineBackend
        )

        self._test_sql_backend_retire(sql_obj)

    def test_grapevine_couch_to_sql(self):
        couch_obj = self._test_couch_backend_create(
            GrapevineBackend,
            None,
            'MOBILE_BACKEND_GRAPEVINE',
            "Grapevine",
            None,
            [],
            True,
            "Grapevine Description",
            ['27'],
            'xxxx',
            extra_fields={
                'affiliate_code': 'abc',
                'authentication_code': 'def',
            }
        )

        self._test_couch_backend_update(
            GrapevineBackend,
            None,
            'MOBILE_BACKEND_GRAPEVINE2',
            "Grapevine2",
            None,
            [],
            True,
            "Grapevine Description2",
            ['27', '266'],
            'xxxxx',
            couch_obj=couch_obj,
            extra_fields={
                'affiliate_code': 'abc2',
                'authentication_code': 'def2',
            }
        )

        self._test_couch_backend_retire(couch_obj)

    def test_http_sql_to_couch(self):
        sql_obj = self._test_sql_backend_create(
            SQLHttpBackend,
            'SMS',
            'HTTP',
            True,
            None,
            'MOBILE_BACKEND_HTTP',
            "Http",
            "Http Description",
            ['*'],
            {
                'url': 'http://127.0.0.1',
                'message_param': 'text',
                'number_param': 'phone',
                'include_plus': True,
                'method': 'GET',
                'additional_params': {'a': 'b', 'c': 'd'},
            },
            None,
            couch_class=HttpBackend
        )

        self._test_sql_backend_update(
            SQLHttpBackend,
            'SMS',
            'HTTP',
            True,
            None,
            'MOBILE_BACKEND_HTTP2',
            "Http2",
            "Http Description2",
            ['*'],
            {
                'url': 'http://127.0.0.1:8000',
                'message_param': 'text2',
                'number_param': 'phone2',
                'include_plus': False,
                'method': 'POST',
                'additional_params': {'a2': 'b2'},
            },
            None,
            sql_obj=sql_obj,
            couch_class=HttpBackend
        )

        self._test_sql_backend_retire(sql_obj)

    def test_http_couch_to_sql(self):
        couch_obj = self._test_couch_backend_create(
            HttpBackend,
            None,
            'MOBILE_BACKEND_HTTP',
            "Http",
            None,
            [],
            True,
            "Http Description",
            [],
            None,
            extra_fields={
                'url': 'http://127.0.0.1',
                'message_param': 'text',
                'number_param': 'phone',
                'include_plus': True,
                'method': 'GET',
                'additional_params': {'a': 'b', 'c': 'd'},
            }
        )

        self._test_couch_backend_update(
            HttpBackend,
            None,
            'MOBILE_BACKEND_HTTP2',
            "Http2",
            None,
            [],
            True,
            "Http Description2",
            [],
            None,
            couch_obj=couch_obj,
            extra_fields={
                'url': 'http://127.0.0.1:8000',
                'message_param': 'text2',
                'number_param': 'phone2',
                'include_plus': False,
                'method': 'POST',
                'additional_params': {'a2': 'b2'},
            }
        )

        self._test_couch_backend_retire(couch_obj)

    def test_mach_sql_to_couch(self):
        sql_obj = self._test_sql_backend_create(
            SQLMachBackend,
            'SMS',
            'MACH',
            True,
            None,
            'MOBILE_BACKEND_MACH',
            "Mach",
            "Mach Description",
            ['*'],
            {
                'account_id': 'a',
                'password': 'b',
                'sender_id': 'c',
                'max_sms_per_second': 1,
            },
            None,
            couch_class=MachBackend
        )

        self._test_sql_backend_update(
            SQLMachBackend,
            'SMS',
            'MACH',
            True,
            None,
            'MOBILE_BACKEND_MACH2',
            "Mach2",
            "Mach Description2",
            ['*'],
            {
                'account_id': 'a2',
                'password': 'b2',
                'sender_id': 'c2',
                'max_sms_per_second': 2,
            },
            None,
            sql_obj=sql_obj,
            couch_class=MachBackend
        )

        self._test_sql_backend_retire(sql_obj)

    def test_mach_couch_to_sql(self):
        couch_obj = self._test_couch_backend_create(
            MachBackend,
            None,
            'MOBILE_BACKEND_MACH',
            "Mach",
            None,
            [],
            True,
            "Mach Description",
            ['*'],
            None,
            extra_fields={
                'account_id': 'a',
                'password': 'b',
                'sender_id': 'c',
                'max_sms_per_second': 1,
            }
        )

        self._test_couch_backend_update(
            MachBackend,
            None,
            'MOBILE_BACKEND_MACH2',
            "Mach2",
            None,
            [],
            True,
            "Mach Description2",
            ['*'],
            None,
            couch_obj=couch_obj,
            extra_fields={
                'account_id': 'a2',
                'password': 'b2',
                'sender_id': 'c2',
                'max_sms_per_second': 2,
            }
        )

        self._test_couch_backend_retire(couch_obj)

    def test_megamobile_sql_to_couch(self):
        sql_obj = self._test_sql_backend_create(
            SQLMegamobileBackend,
            'SMS',
            'MEGAMOBILE',
            True,
            None,
            'MOBILE_BACKEND_MEGAMOBILE',
            "Megamobile",
            "Megamobile Description",
            ['63'],
            {
                'api_account_name': 'a',
                'source_identifier': 'b',
            },
            None,
            couch_class=MegamobileBackend
        )

        self._test_sql_backend_update(
            SQLMegamobileBackend,
            'SMS',
            'MEGAMOBILE',
            True,
            None,
            'MOBILE_BACKEND_MEGAMOBILE2',
            "Megamobile2",
            "Megamobile Description2",
            ['63'],
            {
                'api_account_name': 'a2',
                'source_identifier': 'b2',
            },
            None,
            sql_obj=sql_obj,
            couch_class=MegamobileBackend
        )

        self._test_sql_backend_retire(sql_obj)

    def test_megamobile_couch_to_sql(self):
        couch_obj = self._test_couch_backend_create(
            MegamobileBackend,
            None,
            'MOBILE_BACKEND_MEGAMOBILE',
            "Megamobile",
            None,
            [],
            True,
            "Megamobile Description",
            ['63'],
            None,
            extra_fields={
                'api_account_name': 'a',
                'source_identifier': 'b',
            }
        )

        self._test_couch_backend_update(
            MegamobileBackend,
            None,
            'MOBILE_BACKEND_MEGAMOBILE2',
            "Megamobile2",
            None,
            [],
            True,
            "Megamobile Description2",
            ['63'],
            None,
            couch_obj=couch_obj,
            extra_fields={
                'api_account_name': 'a2',
                'source_identifier': 'b2',
            }
        )

        self._test_couch_backend_retire(couch_obj)

    def test_sislog_sql_to_couch(self):
        sql_obj = self._test_sql_backend_create(
            SQLSislogBackend,
            'SMS',
            'SISLOG',
            True,
            None,
            'MOBILE_BACKEND_SISLOG',
            "Sislog",
            "Sislog Description",
            ['258'],
            {
                'url': 'http://127.0.0.1',
                'message_param': 'text',
                'number_param': 'phone',
                'include_plus': True,
                'method': 'GET',
                'additional_params': {'a': 'b', 'c': 'd'},
            },
            None,
            couch_class=HttpBackend
        )

        self._test_sql_backend_update(
            SQLSislogBackend,
            'SMS',
            'SISLOG',
            True,
            None,
            'MOBILE_BACKEND_SISLOG2',
            "Sislog2",
            "Sislog Description2",
            ['258'],
            {
                'url': 'http://127.0.0.1:8000',
                'message_param': 'text2',
                'number_param': 'phone2',
                'include_plus': False,
                'method': 'POST',
                'additional_params': {'a': 'b', 'c': 'd', 'e': 'f'},
            },
            None,
            sql_obj=sql_obj,
            couch_class=HttpBackend
        )

        self._test_sql_backend_retire(sql_obj)

    def test_sislog_couch_to_sql(self):
        couch_obj = self._test_couch_backend_create(
            HttpBackend,
            None,
            'MOBILE_BACKEND_SISLOG',
            "Sislog",
            'SISLOG',
            [],
            True,
            "Sislog Description",
            ['258'],
            None,
            extra_fields={
                'url': 'http://127.0.0.1',
                'message_param': 'text',
                'number_param': 'phone',
                'include_plus': True,
                'method': 'GET',
                'additional_params': {'a': 'b', 'c': 'd'},
            }
        )

        self._test_couch_backend_update(
            HttpBackend,
            None,
            'MOBILE_BACKEND_SISLOG2',
            "Sislog2",
            'SISLOG',
            [],
            True,
            "Sislog Description2",
            ['258'],
            None,
            couch_obj=couch_obj,
            extra_fields={
                'url': 'http://127.0.0.1:8000',
                'message_param': 'text2',
                'number_param': 'phone2',
                'include_plus': False,
                'method': 'POST',
                'additional_params': {'a': 'b', 'c': 'd', 'e': 'f'},
            }
        )

        self._test_couch_backend_retire(couch_obj)

    def test_smsgh_sql_to_couch(self):
        sql_obj = self._test_sql_backend_create(
            SQLSMSGHBackend,
            'SMS',
            'SMSGH',
            False,
            'smsgh-domain',
            'MOBILE_BACKEND_SMSGH',
            "Smsgh",
            "Smsgh Description",
            [],
            {
                'from_number': 'a',
                'client_id': 'b',
                'client_secret': 'c',
            },
            '0000',
            couch_class=SMSGHBackend
        )

        self._test_sql_backend_update(
            SQLSMSGHBackend,
            'SMS',
            'SMSGH',
            False,
            'smsgh-domain',
            'MOBILE_BACKEND_SMSGH2',
            "Smsgh2",
            "Smsgh Description2",
            [],
            {
                'from_number': 'a2',
                'client_id': 'b2',
                'client_secret': 'c2',
            },
            '0000',
            sql_obj=sql_obj,
            couch_class=SMSGHBackend
        )

        self._test_sql_backend_retire(sql_obj)

    def test_smsgh_couch_to_sql(self):
        couch_obj = self._test_couch_backend_create(
            SMSGHBackend,
            'smsgh-domain',
            'MOBILE_BACKEND_SMSGH',
            "Smsgh",
            None,
            [],
            False,
            "Smsgh Description",
            [],
            '0000',
            extra_fields={
                'from_number': 'a',
                'client_id': 'b',
                'client_secret': 'c',
            }
        )

        self._test_couch_backend_update(
            SMSGHBackend,
            'smsgh-domain',
            'MOBILE_BACKEND_SMSGH2',
            "Smsgh2",
            None,
            [],
            False,
            "Smsgh Description2",
            [],
            '0000',
            couch_obj=couch_obj,
            extra_fields={
                'from_number': 'a2',
                'client_id': 'b2',
                'client_secret': 'c2',
            }
        )

        self._test_couch_backend_retire(couch_obj)

    def test_telerivet_sql_to_couch(self):
        sql_obj = self._test_sql_backend_create(
            SQLTelerivetBackend,
            'SMS',
            'TELERIVET',
            False,
            'telerivet-domain',
            'MOBILE_BACKEND_TELERIVET',
            "Telerivet",
            "Telerivet Description",
            [],
            {
                'api_key': 'a',
                'project_id': 'b',
                'phone_id': 'c',
                'webhook_secret': 'd',
                'country_code': 'x',
            },
            None,
            shared_domains=['d1', 'd2'],
            couch_class=TelerivetBackend
        )

        self._test_sql_backend_update(
            SQLTelerivetBackend,
            'SMS',
            'TELERIVET',
            False,
            'telerivet-domain',
            'MOBILE_BACKEND_TELERIVET2',
            "Telerivet2",
            "Telerivet Description2",
            [],
            {
                'api_key': 'a2',
                'project_id': 'b2',
                'phone_id': 'c2',
                'webhook_secret': 'd2',
                'country_code': 'x2',
            },
            None,
            shared_domains=['d1'],
            sql_obj=sql_obj,
            couch_class=TelerivetBackend
        )

        self._test_sql_backend_retire(sql_obj)

    def test_telerivet_couch_to_sql(self):
        couch_obj = self._test_couch_backend_create(
            TelerivetBackend,
            'telerivet-domain',
            'MOBILE_BACKEND_TELERIVET',
            "Telerivet",
            None,
            ['d1', 'd2'],
            False,
            "Telerivet Description",
            [],
            None,
            extra_fields={
                'api_key': 'a',
                'project_id': 'b',
                'phone_id': 'c',
                'webhook_secret': 'd',
                'country_code': 'x',
            }
        )

        self._test_couch_backend_update(
            TelerivetBackend,
            'telerivet-domain',
            'MOBILE_BACKEND_TELERIVET2',
            "Telerivet2",
            None,
            ['d1'],
            False,
            "Telerivet Description2",
            [],
            None,
            couch_obj=couch_obj,
            extra_fields={
                'api_key': 'a2',
                'project_id': 'b2',
                'phone_id': 'c2',
                'webhook_secret': 'd2',
                'country_code': 'x2',
            }
        )

        self._test_couch_backend_retire(couch_obj)

    def test_test_sql_to_couch(self):
        sql_obj = self._test_sql_backend_create(
            SQLTestSMSBackend,
            'SMS',
            'TEST',
            True,
            None,
            'MOBILE_BACKEND_TEST',
            "Test",
            "Test Description",
            [],
            {},
            None,
            couch_class=TestSMSBackend
        )

        self._test_sql_backend_update(
            SQLTestSMSBackend,
            'SMS',
            'TEST',
            True,
            None,
            'MOBILE_BACKEND_TEST2',
            "Test2",
            "Test Description2",
            [],
            {},
            None,
            sql_obj=sql_obj,
            couch_class=TestSMSBackend
        )

        self._test_sql_backend_retire(sql_obj)

    def test_test_couch_to_sql(self):
        couch_obj = self._test_couch_backend_create(
            TestSMSBackend,
            None,
            'MOBILE_BACKEND_TEST',
            "Test",
            None,
            [],
            True,
            "Test Description",
            [],
            None,
            extra_fields={}
        )

        self._test_couch_backend_update(
            TestSMSBackend,
            None,
            'MOBILE_BACKEND_TEST2',
            "Test2",
            None,
            [],
            True,
            "Test Description2",
            [],
            None,
            couch_obj=couch_obj,
            extra_fields={}
        )

        self._test_couch_backend_retire(couch_obj)

    def test_tropo_sql_to_couch(self):
        sql_obj = self._test_sql_backend_create(
            SQLTropoBackend,
            'SMS',
            'TROPO',
            True,
            None,
            'MOBILE_BACKEND_TROPO',
            "Tropo",
            "Tropo Description",
            ['*'],
            {'messaging_token': 'abc'},
            None,
            couch_class=TropoBackend
        )

        self._test_sql_backend_update(
            SQLTropoBackend,
            'SMS',
            'TROPO',
            True,
            None,
            'MOBILE_BACKEND_TROPO2',
            "Tropo2",
            "Tropo Description2",
            ['*'],
            {'messaging_token': 'abc2'},
            None,
            sql_obj=sql_obj,
            couch_class=TropoBackend
        )

        self._test_sql_backend_retire(sql_obj)

    def test_tropo_couch_to_sql(self):
        couch_obj = self._test_couch_backend_create(
            TropoBackend,
            None,
            'MOBILE_BACKEND_TROPO',
            "Tropo",
            None,
            [],
            True,
            "Tropo Description",
            ['*'],
            None,
            extra_fields={'messaging_token': 'abc'},
        )

        self._test_couch_backend_update(
            TropoBackend,
            None,
            'MOBILE_BACKEND_TROPO2',
            "Tropo2",
            None,
            [],
            True,
            "Tropo Description2",
            ['*'],
            None,
            couch_obj=couch_obj,
            extra_fields={'messaging_token': 'abc2'},
        )

        self._test_couch_backend_retire(couch_obj)

    def test_twilio_sql_to_couch(self):
        sql_obj = self._test_sql_backend_create(
            SQLTwilioBackend,
            'SMS',
            'TWILIO',
            True,
            None,
            'MOBILE_BACKEND_TWILIO',
            "Twilio",
            "Twilio Description",
            ['*'],
            {
                'account_sid': 'a',
                'auth_token': 'b',
            },
            None,
            load_balancing_numbers=['1234', '5678'],
            couch_class=TwilioBackend
        )

        self._test_sql_backend_update(
            SQLTwilioBackend,
            'SMS',
            'TWILIO',
            True,
            None,
            'MOBILE_BACKEND_TWILIO2',
            "Twilio2",
            "Twilio Description2",
            ['*'],
            {
                'account_sid': 'a2',
                'auth_token': 'b2',
            },
            None,
            load_balancing_numbers=['1234'],
            sql_obj=sql_obj,
            couch_class=TwilioBackend
        )

        self._test_sql_backend_retire(sql_obj)

    def test_twilio_couch_to_sql(self):
        couch_obj = self._test_couch_backend_create(
            TwilioBackend,
            None,
            'MOBILE_BACKEND_TWILIO',
            "Twilio",
            None,
            [],
            True,
            "Twilio Description",
            ['*'],
            None,
            load_balancing_numbers=['1234', '5678'],
            extra_fields={
                'account_sid': 'a',
                'auth_token': 'b',
            }
        )

        self._test_couch_backend_update(
            TwilioBackend,
            None,
            'MOBILE_BACKEND_TWILIO2',
            "Twilio2",
            None,
            [],
            True,
            "Twilio Description2",
            ['*'],
            None,
            couch_obj=couch_obj,
            load_balancing_numbers=['1234'],
            extra_fields={
                'account_sid': 'a2',
                'auth_token': 'b2',
            }
        )

        self._test_couch_backend_retire(couch_obj)

    def test_unicel_sql_to_couch(self):
        sql_obj = self._test_sql_backend_create(
            SQLUnicelBackend,
            'SMS',
            'UNICEL',
            True,
            None,
            'MOBILE_BACKEND_UNICEL',
            "Unicel",
            "Unicel Description",
            ['91'],
            {
                'username': 'a',
                'password': 'b',
                'sender': 'c',
            },
            'xxxx',
            couch_class=UnicelBackend
        )

        self._test_sql_backend_update(
            SQLUnicelBackend,
            'SMS',
            'UNICEL',
            True,
            None,
            'MOBILE_BACKEND_UNICEL2',
            "Unicel2",
            "Unicel Description2",
            ['91'],
            {
                'username': 'a2',
                'password': 'b2',
                'sender': 'c2',
            },
            'xxxxx',
            sql_obj=sql_obj,
            couch_class=UnicelBackend
        )

        self._test_sql_backend_retire(sql_obj)

    def test_unicel_couch_to_sql(self):
        couch_obj = self._test_couch_backend_create(
            UnicelBackend,
            None,
            'MOBILE_BACKEND_UNICEL',
            "Unicel",
            None,
            [],
            True,
            "Unicel Description",
            ['91'],
            'xxxx',
            extra_fields={
                'username': 'a',
                'password': 'b',
                'sender': 'c',
            }
        )

        self._test_couch_backend_update(
            UnicelBackend,
            None,
            'MOBILE_BACKEND_UNICEL2',
            "Unicel2",
            None,
            [],
            True,
            "Unicel Description2",
            ['91'],
            'xxxxx',
            couch_obj=couch_obj,
            extra_fields={
                'username': 'a2',
                'password': 'b2',
                'sender': 'c2',
            }
        )

        self._test_couch_backend_retire(couch_obj)

    def test_yo_sql_to_couch(self):
        sql_obj = self._test_sql_backend_create(
            SQLYoBackend,
            'SMS',
            'YO',
            True,
            None,
            'MOBILE_BACKEND_YO',
            "Yo",
            "Yo Description",
            ['256'],
            {
                'url': 'http://127.0.0.1',
                'message_param': 'text',
                'number_param': 'phone',
                'include_plus': True,
                'method': 'GET',
                'additional_params': {'a': 'b', 'c': 'd'},
            },
            None,
            couch_class=HttpBackend
        )

        self._test_sql_backend_update(
            SQLYoBackend,
            'SMS',
            'YO',
            True,
            None,
            'MOBILE_BACKEND_YO2',
            "Yo2",
            "Yo Description2",
            ['256'],
            {
                'url': 'http://127.0.0.1:8000',
                'message_param': 'text2',
                'number_param': 'phone2',
                'include_plus': False,
                'method': 'POST',
                'additional_params': {'a': 'b2', 'c': 'd2'},
            },
            None,
            sql_obj=sql_obj,
            couch_class=HttpBackend
        )

        self._test_sql_backend_retire(sql_obj)

    def test_yo_couch_to_sql(self):
        couch_obj = self._test_couch_backend_create(
            HttpBackend,
            None,
            'MOBILE_BACKEND_YO',
            "Yo",
            'YO',
            [],
            True,
            "Yo Description",
            ['256'],
            None,
            extra_fields={
                'url': 'http://127.0.0.1',
                'message_param': 'text',
                'number_param': 'phone',
                'include_plus': True,
                'method': 'GET',
                'additional_params': {'a': 'b', 'c': 'd'},
            }
        )

        self._test_couch_backend_update(
            HttpBackend,
            None,
            'MOBILE_BACKEND_YO2',
            "Yo2",
            'YO',
            [],
            True,
            "Yo Description2",
            ['256'],
            None,
            couch_obj=couch_obj,
            extra_fields={
                'url': 'http://127.0.0.1:8000',
                'message_param': 'text2',
                'number_param': 'phone2',
                'include_plus': False,
                'method': 'POST',
                'additional_params': {'a': 'b2', 'c': 'd2'},
            }
        )

        self._test_couch_backend_retire(couch_obj)

    def test_kookoo_sql_to_couch(self):
        sql_obj = self._test_sql_backend_create(
            SQLKooKooBackend,
            'IVR',
            'KOOKOO',
            True,
            None,
            'MOBILE_BACKEND_KOOKOO',
            "KooKoo",
            "KooKoo Description",
            ['91'],
            {'api_key': 'abc'},
            None,
            couch_class=KooKooBackend
        )

        self._test_sql_backend_update(
            SQLTropoBackend,
            'IVR',
            'KOOKOO',
            True,
            None,
            'MOBILE_BACKEND_KOOKOO2',
            "KooKoo2",
            "KooKoo Description2",
            ['91'],
            {'api_key': 'abc2'},
            None,
            sql_obj=sql_obj,
            couch_class=KooKooBackend
        )

        self._test_sql_backend_retire(sql_obj)

    def test_kookoo_couch_to_sql(self):
        couch_obj = self._test_couch_backend_create(
            KooKooBackend,
            None,
            'MOBILE_BACKEND_KOOKOO',
            "KooKoo",
            None,
            [],
            True,
            "KooKoo Description",
            ['91'],
            None,
            extra_fields={'api_key': 'abc'},
        )

        self._test_couch_backend_update(
            KooKooBackend,
            None,
            'MOBILE_BACKEND_KOOKOO2',
            "KooKoo2",
            None,
            [],
            True,
            "KooKoo Description2",
            ['91'],
            None,
            couch_obj=couch_obj,
            extra_fields={'api_key': 'abc2'},
        )

        self._test_couch_backend_retire(couch_obj)

    def _compare_backend_maps(self, couch_obj, sql_obj):
        self.assertEqual(couch_obj._id, sql_obj.couch_id)
        self.assertEqual(couch_obj.domain, sql_obj.domain)
        self.assertEqual(couch_obj.is_global, sql_obj.is_global)
        self.assertEqual(couch_obj.prefix, sql_obj.prefix)
        self.assertEqual(couch_obj.backend_type, sql_obj.backend_type)
        self.assertEqual(couch_obj.backend_id, sql_obj.backend.couch_id)

    def _check_backend_counts(self, couch_backends, couch_mappings, sql_backends, sql_mappings):
        self.assertEqual(len(self._get_all_couch_backends()), couch_backends)
        self.assertEqual(len(self._get_all_couch_backend_mappings()), couch_mappings)
        self.assertEqual(self._count_all_sql_backends(), sql_backends)
        self.assertEqual(self._count_all_sql_backend_mappings(), sql_mappings)

    def test_backend_map_couch_to_sql(self):
        couch_backend = TestSMSBackend(is_global=True, name='MOBILE_BACKEND_TEST')
        couch_backend.save()

        # Create
        couch_backend_mapping = BackendMapping(
            domain=None,
            is_global=True,
            prefix='*',
            backend_type='SMS',
            backend_id=couch_backend._id
        )
        couch_backend_mapping.save()
        self._check_backend_counts(1, 1, 1, 1)
        sql_backend_mapping = SQLMobileBackendMapping.objects.get(couch_id=couch_backend_mapping._id)
        self._compare_backend_maps(couch_backend_mapping, sql_backend_mapping)

        # Update
        couch_backend_mapping.prefix = '1'
        couch_backend_mapping.save()
        self._check_backend_counts(1, 1, 1, 1)
        sql_backend_mapping = SQLMobileBackendMapping.objects.get(couch_id=couch_backend_mapping._id)
        self._compare_backend_maps(couch_backend_mapping, sql_backend_mapping)

        # Delete
        couch_backend_mapping.delete()
        self._check_backend_counts(1, 0, 1, 0)

    def test_backend_map_sql_to_couch(self):
        sql_backend = SQLTestSMSBackend(is_global=True, name='MOBILE_BACKEND_TEST')
        sql_backend.save()

        # Create
        sql_backend_mapping = SQLMobileBackendMapping(
            domain=None,
            is_global=True,
            prefix='*',
            backend_type='SMS',
            backend=sql_backend
        )
        sql_backend_mapping.save()
        self._check_backend_counts(1, 1, 1, 1)
        couch_backend_mapping = BackendMapping.get(sql_backend_mapping.couch_id)
        self._compare_backend_maps(couch_backend_mapping, sql_backend_mapping)

        # Update
        sql_backend_mapping.prefix = '1'
        sql_backend_mapping.save()
        self._check_backend_counts(1, 1, 1, 1)
        couch_backend_mapping = BackendMapping.get(sql_backend_mapping.couch_id)
        self._compare_backend_maps(couch_backend_mapping, sql_backend_mapping)

        # Delete
        sql_backend_mapping.delete()
        self._check_backend_counts(1, 0, 1, 0)

    def test_backend_cascade_delete(self):
        sql_backend = SQLTestSMSBackend(is_global=True, name='MOBILE_BACKEND_TEST')
        sql_backend.save()

        sql_backend_mapping = SQLMobileBackendMapping(
            domain=None,
            is_global=True,
            prefix='*',
            backend_type='SMS',
            backend=sql_backend
        )
        sql_backend_mapping.save()
        self._check_backend_counts(1, 1, 1, 1)

        sql_backend.soft_delete()
        self._check_backend_counts(0, 0, 1, 0)

    def _delete_all_backends(self):
        MobileBackend.get_db().bulk_delete([doc.to_json() for doc in self._get_all_couch_backends()])
        BackendMapping.get_db().bulk_delete([doc.to_json() for doc in self._get_all_couch_backend_mappings()])
        MobileBackendInvitation.objects.all().delete()
        SQLMobileBackend.objects.all().delete()
        SQLMobileBackendMapping.objects.all().delete()
