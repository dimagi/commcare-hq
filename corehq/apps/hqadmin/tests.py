# Use modern Python
from __future__ import absolute_import, print_function, unicode_literals

# Django imports
import os
from django.test import TestCase, SimpleTestCase

# External imports
from django_prbac.models import Grant, Role

# CCHQ imports
from corehq.apps.hqadmin.management.commands import cchq_prbac_bootstrap
from corehq.apps.hqadmin.management.commands.make_supervisor_pillowtop_conf import Command


class TestCchqPrbacBootstrap(TestCase):
    """
    Tests the PRBAC bootstrap with and without --dry-run
    """

    def test_dry_run(self):
        """
        When --dry-run is passed, no models should be created
        """
        self.assertEquals(Role.objects.count(), 0)
        self.assertEquals(Grant.objects.count(), 0)

        command = cchq_prbac_bootstrap.Command()
        command.handle(dry_run=True)

        self.assertEquals(Role.objects.count(), 0)
        self.assertEquals(Grant.objects.count(), 0)

    def test_non_dry_run(self):
        """
        When there is no --dry-run passed, it defaults to false, and
        things happen. Furthermore, the thing should be idempotent
        """
        self.assertEquals(Role.objects.count(), 0)
        self.assertEquals(Grant.objects.count(), 0)

        command = cchq_prbac_bootstrap.Command()
        command.handle(dry_run=False)

        # Just make sure something happened
        self.assertGreater(Role.objects.count(), 10)
        self.assertGreater(Grant.objects.count(), 10)

        role_count = Role.objects.count()
        grant_count = Grant.objects.count()

        command.handle(dry_run=False)

        self.assertEquals(Role.objects.count(), role_count)
        self.assertEquals(Grant.objects.count(), grant_count)


class TestPillowTopFiltering(SimpleTestCase):
    """
    Tests the function that excludes certain pillows from running on staging.
    """

    def setUp(self):
        self.pillowtops = {
            'core': [
                'corehq.pillows.case.CasePillow',
                'corehq.pillows.xform.XFormPillow',
                'corehq.pillows.domain.DomainPillow',
                'corehq.pillows.user.UserPillow',
                'corehq.pillows.application.AppPillow',
                'corehq.pillows.group.GroupPillow',
                'corehq.pillows.sms.SMSPillow',
                'corehq.pillows.user.GroupToUserPillow',
                'corehq.pillows.user.UnknownUsersPillow',
                'corehq.pillows.sofabed.FormDataPillow',
                'corehq.pillows.sofabed.CaseDataPillow',
            ],
            'phonelog': [
                'corehq.pillows.log.PhoneLogPillow',
            ],
        }

        self.here = os.path.dirname(os.path.realpath(__file__))

    def test_no_blacklist_items(self):
        expected_pillows = [u'corehq.pillows.case.CasePillow',
                            u'corehq.pillows.xform.XFormPillow',
                            u'corehq.pillows.domain.DomainPillow',
                            u'corehq.pillows.user.UserPillow',
                            u'corehq.pillows.application.AppPillow',
                            u'corehq.pillows.group.GroupPillow',
                            u'corehq.pillows.sms.SMSPillow',
                            u'corehq.pillows.user.GroupToUserPillow',
                            u'corehq.pillows.user.UnknownUsersPillow',
                            u'corehq.pillows.sofabed.FormDataPillow',
                            u'corehq.pillows.sofabed.CaseDataPillow',
                            u'corehq.pillows.log.PhoneLogPillow', ]

        self.assertEqual(expected_pillows, Command.get_pillows_from_settings(self.pillowtops))

    def test_with_blacklist_items(self):
        expected_pillows = [u'corehq.pillows.case.CasePillow',
                            u'corehq.pillows.xform.XFormPillow',
                            u'corehq.pillows.domain.DomainPillow',
                            u'corehq.pillows.user.UserPillow',
                            u'corehq.pillows.application.AppPillow',
                            u'corehq.pillows.group.GroupPillow',
                            u'corehq.pillows.sms.SMSPillow',
                            u'corehq.pillows.user.GroupToUserPillow',
                            u'corehq.pillows.user.UnknownUsersPillow',
                            u'corehq.pillows.sofabed.FormDataPillow',
                            u'corehq.pillows.sofabed.CaseDataPillow', ]

        self.assertEqual(expected_pillows, Command.get_pillows_from_settings(self.pillowtops,
                                                                             {'pillowtop_blacklist': ['phonelog']}))

    def test_loading_existing_conf_file(self):
        expected_reject = {'pillowtop_blacklist': ['fluff']}

        reject = Command.get_rejected_pillow_types(os.path.join(self.here, '..', '..', '..'), 'staging')
        self.assertEqual(reject, expected_reject)

    def test_loading_no_existing_conf_file(self):
        expected_reject = {}

        reject = Command.get_rejected_pillow_types(os.path.join(self.here, '..', '..', '..'), 'production')
        self.assertEqual(reject, expected_reject)

    def test_india_server_exclusions(self):
        self.pillowtops['fluff'] = [
            'custom.bihar.models.CareBiharFluffPillow',
            'custom.opm.models.OpmCaseFluffPillow',
            'custom.opm.models.OpmUserFluffPillow',
        ]

        reject = Command.get_rejected_pillow_types(os.path.join(self.here, '..', '..', '..'), 'india')
        pillows = Command.get_pillows_from_settings(self.pillowtops, reject)
        has_bihar_pillow = False
        for pillow in pillows:
            assert pillow != 'custom.opm.models.OpmCaseFluffPillow'
            if pillow == 'custom.bihar.models.CareBiharFluffPillow':
                has_bihar_pillow = True
        assert has_bihar_pillow
