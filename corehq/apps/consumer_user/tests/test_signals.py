import uuid
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.test.utils import override_settings

from mock import patch

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure

from corehq.apps.consumer_user.const import (
    CONSUMER_INVITATION_CASE_TYPE,
    CONSUMER_INVITATION_STATUS,
)
from corehq.apps.consumer_user.models import (
    ConsumerUser,
    ConsumerUserCaseRelationship,
    ConsumerUserInvitation,
)
from corehq.apps.consumer_user.tasks import expire_unused_invitations
from corehq.apps.data_interfaces.tests.util import create_case
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.tests.locks import reentrant_redis_locks


class SignalTestCase(TestCase):

    def setUp(self):
        self.domain = 'consumer-invitation-test'
        self.factory = CaseFactory(self.domain)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases(self.domain)
        FormProcessorTestUtils.delete_all_xforms(self.domain)
        ConsumerUserCaseRelationship.objects.all().delete()
        ConsumerUserInvitation.objects.all().delete()
        ConsumerUser.objects.all().delete()
        User.objects.all().delete()
        super().tearDown()

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    @reentrant_redis_locks()
    def test_method_send_email_new_case(self):
        with patch('corehq.apps.hqwebapp.tasks.send_html_email_async.delay') as send_html_email_async:
            result = self.factory.create_or_update_case(
                CaseStructure(
                    case_id=uuid.uuid4().hex,
                    indices=[
                        CaseIndex(
                            CaseStructure(case_id=uuid.uuid4().hex, attrs={'create': True}),
                            relationship=CASE_INDEX_EXTENSION
                        )
                    ],
                    attrs={
                        'create': True,
                        'case_type': CONSUMER_INVITATION_CASE_TYPE,
                        'owner_id': 'comm_care',
                        'update': {
                            'email': 'testing@testing.in'
                        }
                    }
                )
            )
            # Creating new comm care case creates a new ConsumerUserInvitation
            case = result[0]
            customer_invitation = ConsumerUserInvitation.objects.get(case_id=case.case_id, domain=case.domain)
            self.assertEqual(customer_invitation.email, case.get_case_property('email'))
            self.assertEqual(ConsumerUserInvitation.objects.count(), 1)
            self.assertEqual(ConsumerUserInvitation.objects.filter(active=True).count(), 1)
            self.assertEqual(send_html_email_async.call_count, 1)

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    @reentrant_redis_locks()
    def test_method_send_email_update_other_case_properties(self):
        with patch('corehq.apps.hqwebapp.tasks.send_html_email_async.delay') as send_html_email_async:
            result = self.factory.create_or_update_case(
                CaseStructure(
                    case_id=uuid.uuid4().hex,
                    indices=[
                        CaseIndex(
                            CaseStructure(case_id=uuid.uuid4().hex, attrs={'create': True}),
                            relationship=CASE_INDEX_EXTENSION
                        )
                    ],
                    attrs={
                        'create': True,
                        'case_type': CONSUMER_INVITATION_CASE_TYPE,
                        'owner_id': 'comm_care',
                        'update': {
                            'email': 'testing@testing.in'
                        }
                    }
                )
            )
            case = result[0]
            self.assertEqual(ConsumerUserInvitation.objects.count(), 1)
            self.assertEqual(ConsumerUserInvitation.objects.filter(active=True).count(), 1)
            self.assertEqual(send_html_email_async.call_count, 1)
            # Updating the case properties other than email should not create a new invitation
            self.factory.update_case(
                case.case_id,
                update={'contact_phone_number': '12345'},
            )
            self.assertEqual(ConsumerUserInvitation.objects.count(), 1)
            self.assertEqual(ConsumerUserInvitation.objects.filter(active=True).count(), 1)
            self.assertEqual(send_html_email_async.call_count, 1)

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    @reentrant_redis_locks()
    def test_multiple_invitations_same_demographic_case(self):
        # Only create a single invitation for one demographic case
        parent_id = uuid.uuid4().hex
        self.factory.create_or_update_cases([
            CaseStructure(
                case_id=uuid.uuid4().hex,
                indices=[
                    CaseIndex(
                        CaseStructure(case_id=parent_id, attrs={'create': True}),
                        relationship=CASE_INDEX_EXTENSION
                    )
                ],
                attrs={
                    'create': True,
                    'case_type': CONSUMER_INVITATION_CASE_TYPE,
                    'owner_id': 'comm_care',
                    'update': {
                        'email': 'testing@testing.in'
                    }
                }
            )])
        self.factory.create_or_update_cases([
            CaseStructure(
                case_id=uuid.uuid4().hex,
                indices=[
                    CaseIndex(
                        CaseStructure(case_id=parent_id, attrs={'create': True}),
                        relationship=CASE_INDEX_EXTENSION
                    )
                ],
                attrs={
                    'create': True,
                    'case_type': CONSUMER_INVITATION_CASE_TYPE,
                    'owner_id': 'comm_care',
                    'update': {
                        'email': 'testing2@testing.in'
                    }
                }
            )
        ])
        self.assertEqual(ConsumerUserInvitation.objects.count(), 1)
        self.assertEqual(ConsumerUserInvitation.objects.first().email, "testing@testing.in")

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    @reentrant_redis_locks()
    def test_method_send_email_update_email(self):
        with patch('corehq.apps.hqwebapp.tasks.send_html_email_async.delay') as send_html_email_async:
            result = self.factory.create_or_update_case(
                CaseStructure(
                    case_id=uuid.uuid4().hex,
                    indices=[
                        CaseIndex(
                            CaseStructure(case_id=uuid.uuid4().hex, attrs={'create': True}),
                            relationship=CASE_INDEX_EXTENSION
                        )
                    ],
                    attrs={
                        'create': True,
                        'case_type': CONSUMER_INVITATION_CASE_TYPE,
                        'owner_id': 'comm_care',
                        'update': {
                            'email': 'testing@testing.in'
                        }
                    }
                )
            )
            case = result[0]
            self.assertEqual(ConsumerUserInvitation.objects.count(), 1)
            self.assertEqual(ConsumerUserInvitation.objects.filter(active=True).count(), 1)
            self.assertEqual(send_html_email_async.call_count, 1)
            # Updating the case again with a changed email address creates a new invitation
            self.factory.update_case(
                case.case_id,
                update={
                    'email': 'email@changed.in',
                    CONSUMER_INVITATION_STATUS: 'resend',
                },
            )
            self.assertEqual(ConsumerUserInvitation.objects.count(), 2)
            self.assertEqual(ConsumerUserInvitation.objects.filter(active=True).count(), 1)
            self.assertEqual(send_html_email_async.call_count, 2)

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    @reentrant_redis_locks()
    def test_method_send_email_resend(self):
        with patch('corehq.apps.hqwebapp.tasks.send_html_email_async.delay') as send_html_email_async:
            result = self.factory.create_or_update_case(
                CaseStructure(
                    case_id=uuid.uuid4().hex,
                    indices=[
                        CaseIndex(
                            CaseStructure(case_id=uuid.uuid4().hex, attrs={'create': True}),
                            relationship=CASE_INDEX_EXTENSION
                        )
                    ],
                    attrs={
                        'create': True,
                        'case_type': CONSUMER_INVITATION_CASE_TYPE,
                        'owner_id': 'comm_care',
                        'update': {
                            'email': 'testing@testing.in'
                        }
                    }
                )
            )
            case = result[0]
            self.assertEqual(ConsumerUserInvitation.objects.count(), 1)
            self.assertEqual(ConsumerUserInvitation.objects.filter(active=True).count(), 1)
            self.assertEqual(send_html_email_async.call_count, 1)
            # Updating the case again with status other than sent or accepted should send email again
            self.factory.update_case(
                case.case_id,
                update={CONSUMER_INVITATION_STATUS: 'resend'},
            )
            self.assertEqual(ConsumerUserInvitation.objects.count(), 2)
            self.assertEqual(ConsumerUserInvitation.objects.filter(active=True).count(), 1)
            self.assertEqual(send_html_email_async.call_count, 2)

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    @reentrant_redis_locks()
    def test_method_send_email_closed_case(self):
        with patch('corehq.apps.hqwebapp.tasks.send_html_email_async.delay') as send_html_email_async:
            result = self.factory.create_or_update_case(
                CaseStructure(
                    case_id=uuid.uuid4().hex,
                    indices=[
                        CaseIndex(
                            CaseStructure(case_id=uuid.uuid4().hex, attrs={'create': True}),
                            relationship=CASE_INDEX_EXTENSION
                        )
                    ],
                    attrs={
                        'create': True,
                        'case_type': CONSUMER_INVITATION_CASE_TYPE,
                        'owner_id': 'comm_care',
                        'update': {
                            'email': 'testing@testing.in'
                        }
                    }
                )
            )
            case = result[0]
            self.assertEqual(ConsumerUserInvitation.objects.count(), 1)
            self.assertEqual(ConsumerUserInvitation.objects.filter(active=True).count(), 1)
            self.assertEqual(send_html_email_async.call_count, 1)
            # Closing the case should make invitation inactive
            self.factory.close_case(case.case_id)
            self.assertEqual(ConsumerUserInvitation.objects.count(), 1)
            self.assertEqual(ConsumerUserInvitation.objects.filter(active=True).count(), 0)
            self.assertEqual(ConsumerUserInvitation.objects.filter(active=False).count(), 1)
            self.assertEqual(send_html_email_async.call_count, 1)

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_method_send_email_other_casetype(self):
        invitation_count = ConsumerUserInvitation.objects.count()
        with patch('corehq.apps.hqwebapp.tasks.send_html_email_async.delay') as send_html_email_async, create_case(
            self.domain,
            'person',
            owner_id='comm_care',
        ) as case:
            self.assertEqual(
                ConsumerUserInvitation.objects.filter(case_id=case.case_id, domain=case.domain).count(), 0
            )
            self.assertEqual(ConsumerUserInvitation.objects.count(), invitation_count)
            send_html_email_async.assert_not_called()


class ExpireConsumerUserInvitations(TestCase):
    def setUp(self):
        self.domain = 'consumer-invitation-test'
        self.factory = CaseFactory(self.domain)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases(self.domain)
        FormProcessorTestUtils.delete_all_xforms(self.domain)
        ConsumerUserInvitation.objects.all().delete()
        ConsumerUser.objects.all().delete()
        User.objects.all().delete()
        super().tearDown()

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    @reentrant_redis_locks()
    def test_expired(self):
        result = self.factory.create_or_update_case(
            CaseStructure(
                case_id=uuid.uuid4().hex,
                indices=[
                    CaseIndex(
                        CaseStructure(case_id=uuid.uuid4().hex, attrs={'create': True}),
                        relationship=CASE_INDEX_EXTENSION
                    )
                ],
                attrs={
                    'create': True,
                    'case_type': CONSUMER_INVITATION_CASE_TYPE,
                    'owner_id': 'comm_care',
                    'update': {
                        'email': 'testing@testing.in'
                    }
                }
            )
        )
        case = result[0]
        invitation = ConsumerUserInvitation.objects.get(case_id=case.case_id, domain=case.domain)
        invitation.invited_on = datetime.utcnow() - timedelta(days=32)
        invitation.save(update_fields=['invited_on'])

        expire_unused_invitations()
        invitation.refresh_from_db()
        self.assertFalse(invitation.active)

        case = CaseAccessors(case.domain).get_case(case.case_id)
        self.assertTrue(case.closed)

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    @reentrant_redis_locks()
    def test_not_expired(self):
        result = self.factory.create_or_update_case(
            CaseStructure(
                case_id=uuid.uuid4().hex,
                indices=[
                    CaseIndex(
                        CaseStructure(case_id=uuid.uuid4().hex, attrs={'create': True}),
                        relationship=CASE_INDEX_EXTENSION
                    )
                ],
                attrs={
                    'create': True,
                    'case_type': CONSUMER_INVITATION_CASE_TYPE,
                    'owner_id': 'comm_care',
                    'update': {
                        'email': 'testing@testing.in'
                    }
                }
            )
        )
        case = result[0]
        expire_unused_invitations()
        invitation = ConsumerUserInvitation.objects.get(case_id=case.case_id, domain=case.domain)
        self.assertTrue(invitation.active)

        case = CaseAccessors(case.domain).get_case(case.case_id)
        self.assertFalse(case.closed)
