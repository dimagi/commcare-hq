from casexml.apps.case.mock import CaseFactory
from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.app_manager.util import enable_usercase
from corehq.apps.callcenter.sync_user_case import sync_user_cases
from corehq.apps.data_interfaces.tests.test_auto_case_updates import BaseCaseRuleTest
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import normalize_username
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import (
    FormProcessorTestUtils,
    set_case_property_directly,
    use_sql_backend,
)
from corehq.pillows.case_search import transform_case_for_elasticsearch
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.es.elasticsearch import ConnectionError
from corehq.util.test_utils import trap_extra_setup
from custom.covid.rules.custom_criteria import associated_user_cases_closed


@use_sql_backend
class DeactivatedMobileWorkersTest(BaseCaseRuleTest):
    def setUp(self):
        super().setUp()
        delete_all_users()

        self.domain = "covid-deactivated-mobile-workers"
        self.domain_obj = create_domain(self.domain)
        enable_usercase(self.domain)

        with trap_extra_setup(ConnectionError):
            self.es = get_es_new()
            initialize_index_and_mapping(self.es, CASE_SEARCH_INDEX_INFO)
        self.case_accessor = CaseAccessors(self.domain)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()
        delete_all_users()
        ensure_index_deleted(CASE_SEARCH_INDEX_INFO.index)
        super().tearDown()

    def test_associated_usercase_closed(self):
        username = normalize_username("mobile_worker_1", self.domain)
        mobile_worker = CommCareUser.create(self.domain, username, "123", None, None)
        sync_user_cases(mobile_worker)

        usercase_ids = self.case_accessor.get_case_ids_in_domain(type=USERCASE_TYPE)
        for usercase_id in usercase_ids:
            CaseFactory(self.domain).close_case(usercase_id)
            usercase = self.case_accessor.get_case(usercase_id)
            send_to_elasticsearch(
                "case_search", transform_case_for_elasticsearch(usercase.to_json())
            )
        self.es.indices.refresh(CASE_SEARCH_INDEX_INFO.index)

        checkin_case = CaseFactory(self.domain).create_case(
            case_type="checkin",
            owner_id=mobile_worker.get_id,
            update={"username": mobile_worker.raw_username},
        )
        send_to_elasticsearch(
            "case_search", transform_case_for_elasticsearch(checkin_case.to_json())
        )

        self.assertTrue(associated_user_cases_closed(checkin_case, None))
