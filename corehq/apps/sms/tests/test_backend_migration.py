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

    def _delete_all_backends(self):
        MobileBackend.get_db().bulk_delete([doc.to_json() for doc in self._get_all_couch_backends()])
        MobileBackendInvitation.objects.all().delete()
        SQLMobileBackend.objects.all().delete()
