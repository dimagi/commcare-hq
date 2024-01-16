import uuid
from datetime import datetime, timedelta

from django.test import TestCase

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseBlock, CaseFactory, CaseStructure, CaseIndex
from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.domain.shortcuts import create_user, create_domain
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.registry.tests.utils import create_registry_for_test, Invitation, Grant
from corehq.apps.users.models import CommCareUser
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.models import DataRegistryCaseUpdateRepeater, SQLRepeatRecord
from corehq.motech.repeaters.repeater_generators import DataRegistryCaseUpdatePayloadGenerator
from corehq.motech.repeaters.tests.test_data_registry_case_update_payload_generator import IntentCaseBuilder, \
    DataRegistryUpdateForm
from corehq.util.test_utils import flag_enabled


@flag_enabled('DATA_REGISTRY_CASE_UPDATE_REPEATER')
class DataRegistryCaseUpdateRepeaterTest(TestCase, TestXmlMixin, DomainSubscriptionMixin):
    domain = "source_domain"
    target_domain = "target_domain"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(clear_plan_version_cache)
        cls.addClassCleanup(cls.domain_obj.delete)

        # DATA_FORWARDING is on PRO and above
        cls.setup_subscription(cls.domain, SoftwarePlanEdition.PRO)
        cls.addClassCleanup(cls.teardown_subscriptions)

        cls.connx = ConnectionSettings.objects.create(
            domain=cls.domain,
            url="case-repeater-url/{domain}/",
            username="user1"
        )
        cls.repeater = DataRegistryCaseUpdateRepeater(
            domain=cls.domain,
            connection_settings_id=cls.connx.id,
            white_listed_case_types=[IntentCaseBuilder.CASE_TYPE],
        )
        cls.repeater.save()

        cls.user = create_user("admin", "123")
        cls.registry_slug = create_registry_for_test(
            cls.user,
            cls.domain,
            invitations=[
                Invitation(cls.target_domain),
            ],
            grants=[
                Grant(cls.target_domain, [cls.domain]),
            ],
            name="reg1",
            case_types=["patient"]
        ).slug

        cls.mobile_user = CommCareUser.create(cls.domain, "user1", "123", None, None, is_admin=True)
        cls.addClassCleanup(cls.mobile_user.delete, None, None)

        cls.target_case_id_1 = uuid.uuid4().hex
        cls.target_case_id_2 = uuid.uuid4().hex
        submit_case_blocks(
            [
                CaseBlock(
                    case_id=case_id,
                    create=True,
                    case_type="patient",
                ).as_text()
                for case_id in [cls.target_case_id_1, cls.target_case_id_2]
            ],
            domain=cls.target_domain
        )

    def test_update_cases(self):
        builder1 = (
            IntentCaseBuilder(self.registry_slug)
            .target_case(self.target_domain, self.target_case_id_1)
            .case_properties(new_prop="new_val_case1")
        )
        builder2 = (
            IntentCaseBuilder(self.registry_slug)
            .target_case(self.target_domain, self.target_case_id_2)
            .case_properties(new_prop="new_val_case2")
        )
        factory = CaseFactory(self.domain)
        host = CaseStructure(
            attrs={"create": True, "case_type": "registry_case_update", "update": builder1.props},
        )
        extension = CaseStructure(
            attrs={"create": True, "case_type": "registry_case_update", "update": builder2.props},
            indices=[CaseIndex(
                host,
                relationship=CASE_INDEX_EXTENSION,
            )]
        )
        cases = factory.create_or_update_case(extension, user_id=self.mobile_user.get_id)
        extension_case, host_case = cases

        # test that the extension case doesn't match the 'allow' criteria
        self.assertFalse(self.repeater.allowed_to_forward(extension_case))

        repeat_records = self.repeat_records(self.domain).all()
        self.assertEqual(len(repeat_records), 1)
        payload = repeat_records[0].get_payload()
        form = DataRegistryUpdateForm(payload, host_case)
        form.assert_case_updates({
            self.target_case_id_1: {"new_prop": "new_val_case1"},
            self.target_case_id_2: {"new_prop": "new_val_case2"}
        })

        url = self.repeater.get_url(repeat_records[0])
        self.assertEqual(url, f"case-repeater-url/{self.target_domain}/")

        # check that the synchronous attempt of the repeat record happened
        self.assertEqual(1, len(repeat_records[0].attempts))

    def test_prevention_of_update_chaining(self):
        builder = (
            IntentCaseBuilder(self.registry_slug)
            .target_case(self.target_domain, self.target_case_id_1)
            .case_properties(new_prop="new_val_case1")
        )
        case_struct = CaseStructure(
            attrs={"create": True, "case_type": "registry_case_update", "update": builder.props},
        )
        [case] = CaseFactory(self.domain).create_or_update_case(
            case_struct, user_id=self.mobile_user.get_id,
            # pretend this form came from a repeater in another domain
            xmlns=DataRegistryCaseUpdatePayloadGenerator.XMLNS
        )

        self.assertFalse(self.repeater.allowed_to_forward(case))

        repeat_records = self.repeat_records(self.domain).all()
        self.assertEqual(len(repeat_records), 0)

    @classmethod
    def repeat_records(cls, domain_name):
        # Enqueued repeat records have next_check set 48 hours in the future.
        later = datetime.utcnow() + timedelta(hours=48 + 1)
        return SQLRepeatRecord.objects.filter(domain=domain_name, next_check__lt=later)
