from __future__ import absolute_import
from __future__ import unicode_literals
import os
from django.test import TestCase
from django.test.utils import override_settings
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.util import delete_all_xforms, delete_all_cases
from corehq.apps.domain.models import Domain
from corehq.apps.domain_migration_flags.models import DomainMigrationProgress
from corehq.util.test_utils import TestFileMixin
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.dbaccessors import get_cases_in_domain
from corehq.apps.receiverwrapper.exceptions import LocalSubmissionError
from corehq.apps.tzmigration.api import set_tz_migration_complete, \
    set_tz_migration_started, MigrationStatus, TZMIGRATION_SLUG
from corehq.apps.tzmigration.timezonemigration import \
    run_timezone_migration_for_domain, _run_timezone_migration_for_domain
from corehq.apps.receiverwrapper.util import submit_form_locally
from couchforms.dbaccessors import get_forms_by_type
from couchforms.models import XFormInstance
from six.moves import zip
import six


class TimeZoneMigrationTest(TestCase, TestFileMixin):

    file_path = 'data',
    root = os.path.dirname(__file__)

    maxDiff = None

    def assertDictEqual(self, d1, d2, msg=None):
        k1 = set(d1.keys())
        k2 = set(d2.keys())
        self.assertEqual(
            k1, k2,
            '{} in first but not in second; {} in second but not in first'
            .format(k1 - k2, k2 - k1)
        )
        for key in k1:
            self.assertEqual(d1[key], d2[key], (
                '{}[{!r}]'.format(msg + ': ' if msg else '', key)
            ))

    def setUp(self):
        for domain in Domain.get_all():
            domain.delete()
        super(TimeZoneMigrationTest, self).setUp()
        self.domain = 'foo'
        self.domain_object = create_domain(self.domain)
        tzp, _ = DomainMigrationProgress.objects.get_or_create(domain=self.domain, migration_slug=TZMIGRATION_SLUG)
        tzp.migration_status = MigrationStatus.NOT_STARTED
        tzp.save()

    def tearDown(self):
        delete_all_xforms()
        delete_all_cases()
        self.domain_object.delete()
        DomainMigrationProgress.objects.all().delete()
        super(TimeZoneMigrationTest, self).tearDown()

    def _compare_forms(self, actual_json, expected_json, msg):
        expected_json.update({
            'domain': self.domain,
            'received_on': actual_json['received_on'],
            'server_modified_on': actual_json['server_modified_on'],
            '_rev': actual_json['_rev'],
            'initial_processing_complete': True,
            '#export_tag': actual_json['#export_tag'],
            'auth_context': actual_json['auth_context'],
        })
        for name, meta in six.iteritems(actual_json.get("external_blobs", {})):
            expected_json["external_blobs"][name]["blobmeta_id"] = meta["blobmeta_id"]
            expected_json["external_blobs"][name]["key"] = meta["key"]
        expected_json = XFormInstance.wrap(expected_json).to_json()
        self.assertDictEqual(actual_json, expected_json, msg)

    def _compare_cases(self, actual_json, expected_json, msg):
        expected_json.update({
            'domain': self.domain,
            '_rev': actual_json['_rev'],
            'initial_processing_complete': True,
            '#export_tag': actual_json['#export_tag'],
            'server_modified_on': actual_json['server_modified_on']
        })
        for expected_action, actual_action in zip(expected_json['actions'], actual_json['actions']):
            expected_action['server_date'] = actual_action['server_date']

        expected_json = CommCareCase.wrap(expected_json).to_json()
        self.assertDictEqual(actual_json, expected_json, msg)

    def test_migration(self):
        xform = self.get_xml('form')
        form_bad_tz = self.get_json('form')
        case_bad_tz = self.get_json('case')
        form_good_tz = self.get_json('form-tz')
        case_good_tz = self.get_json('case-tz')
        with override_settings(PHONE_TIMEZONES_HAVE_BEEN_PROCESSED=False,
                               PHONE_TIMEZONES_SHOULD_BE_PROCESSED=False):
            submit_form_locally(xform, self.domain)

        # Form before
        xform_instance, = get_forms_by_type(self.domain, 'XFormInstance', limit=10)
        xform_json = xform_instance.to_json()
        self._compare_forms(xform_json, form_bad_tz,
                            "Form before migration does not match")

        # Case before
        case, = get_cases_in_domain(self.domain)
        self._compare_cases(case.to_json(), case_bad_tz,
                            "Case before migration does not match")
        run_timezone_migration_for_domain(self.domain)

        # Form after
        xform_instance, = get_forms_by_type(self.domain, 'XFormInstance', limit=10)
        xform_json = xform_instance.to_json()
        self._compare_forms(xform_json, form_good_tz,
                            "Form after migration does not match")

        # Case after
        case, = get_cases_in_domain(self.domain)
        self._compare_cases(case.to_json(), case_good_tz,
                            "Case after migration does not match")

    def test_pause(self):
        xform = self.get_xml('form')
        set_tz_migration_started(self.domain)
        with self.assertRaisesRegex(LocalSubmissionError, 'status code 503'):
            submit_form_locally(xform, self.domain)
        _run_timezone_migration_for_domain(self.domain)
        set_tz_migration_complete(self.domain)
        # no issue
        submit_form_locally(xform, self.domain)
