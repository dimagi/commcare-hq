import json
from corehq.apps.sms.mixin import MobileBackend, SMSLoadBalancingMixin
from corehq.apps.sms.models import SQLMobileBackend, MobileBackendInvitation
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
        return (MobileBackend.view('sms/global_backends', include_docs=True, reduce=False).all() +
                MobileBackend.view('sms/backend_by_domain', include_docs=True, reduce=False).all())

    def _count_all_sql_backends(self):
        return SQLMobileBackend.objects.count()

    def _count_all_sql_backend_invitations(self):
        return MobileBackendInvitation.objects.count()

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
        sql_obj.supported_countries = json.dumps(supported_countries)
        sql_obj.set_extra_fields(**extra_fields)
        sql_obj.reply_to_phone_number = reply_to_phone_number

        if load_balancing_numbers:
            sql_obj.load_balancing_numbers = json.dumps(load_balancing_numbers)

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
        self.assertEqual(couch_obj.supported_countries, json.loads(sql_obj.supported_countries))
        self.assertEqual(couch_obj.reply_to_phone_number, sql_obj.reply_to_phone_number)
        self.assertEqual(couch_obj.backend_type, sql_obj.backend_type)

        for k, v in sql_obj.get_extra_fields().iteritems():
            self.assertEqual(getattr(couch_obj, k), v)

        load_balancing_numbers = json.loads(sql_obj.load_balancing_numbers)
        if load_balancing_numbers:
            self.assertEqual(couch_obj.x_phone_numbers, load_balancing_numbers)

    def _compare_sql_backend(self, couch_obj, sql_obj, extra_fields):
        self.assertEqual(sql_obj.backend_type, couch_obj.backend_type)
        self.assertEqual(sql_obj.hq_api_id, couch_obj.incoming_api_id or couch_obj.get_api_id())
        self.assertEqual(sql_obj.is_global, couch_obj.is_global)
        self.assertEqual(sql_obj.domain, couch_obj.domain)
        self.assertEqual(sql_obj.name, couch_obj.name)
        self.assertEqual(sql_obj.display_name, couch_obj.display_name)
        self.assertEqual(sql_obj.description, couch_obj.description)
        self.assertEqual(json.loads(sql_obj.supported_countries), couch_obj.supported_countries)
        self.assertEqual(json.loads(sql_obj.extra_fields), extra_fields)
        self.assertEqual(sql_obj.deleted, False)
        self.assertEqual(sql_obj.reply_to_phone_number, couch_obj.reply_to_phone_number)
        if isinstance(couch_obj, SMSLoadBalancingMixin):
            self.assertEqual(json.loads(sql_obj.load_balancing_numbers), couch_obj.phone_numbers)
        else:
            self.assertEqual(sql_obj.load_balancing_numbers, '[]')

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

    def _delete_all_backends(self):
        MobileBackend.get_db().bulk_delete([doc.to_json() for doc in self._get_all_couch_backends()])
        MobileBackendInvitation.objects.all().delete()
        SQLMobileBackend.objects.all().delete()
