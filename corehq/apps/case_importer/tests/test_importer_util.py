from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase, override_settings
import mock
from corehq.apps.case_importer.util import is_valid_owner, \
    get_case_properties_for_case_type
from corehq.apps.export.models import CaseExportDataSchema, ExportGroupSchema, \
    MAIN_TABLE, ExportItem, PathNode
from corehq.apps.users.models import CommCareUser, DomainMembership, WebUser


class ImporterUtilsTest(SimpleTestCase):

    def test_user_owner_match(self):
        self.assertTrue(is_valid_owner(_mk_user(domain='match'), 'match'))

    def test_user_owner_nomatch(self):
        self.assertFalse(is_valid_owner(_mk_user(domain='match'), 'nomatch'))

    def test_web_user_owner_match(self):
        self.assertTrue(is_valid_owner(_mk_web_user(domains=['match', 'match2']), 'match'))
        self.assertTrue(is_valid_owner(_mk_web_user(domains=['match', 'match2']), 'match2'))

    def test_web_user_owner_nomatch(self):
        self.assertFalse(is_valid_owner(_mk_web_user(domains=['match', 'match2']), 'nomatch'))

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_get_case_properties_for_case_type(self):
        schema = CaseExportDataSchema(
            group_schemas=[
                ExportGroupSchema(
                    path=MAIN_TABLE,
                    items=[
                        ExportItem(
                            path=[PathNode(name='name')],
                            label='name',
                            last_occurrences={},
                        ),
                        ExportItem(
                            path=[PathNode(name='color')],
                            label='color',
                            last_occurrences={},
                        ),
                    ],
                    last_occurrences={},
                ),
            ],
        )

        with mock.patch(
                'corehq.apps.export.models.new.CaseExportDataSchema.generate_schema_from_builds',
                return_value=schema):
            case_types = get_case_properties_for_case_type('test-domain', 'case-type')

        self.assertEqual(sorted(case_types), ['color', 'name'])


def _mk_user(domain):
    return CommCareUser(domain=domain, domain_membership=DomainMembership(domain=domain))


def _mk_web_user(domains):
    return WebUser(domains=domains, domain_memberships=[DomainMembership(domain=domain) for domain in domains])
