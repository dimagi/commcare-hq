from __future__ import absolute_import
from __future__ import unicode_literals
import datetime

from django.utils import translation
from django.utils.translation import ugettext as _

from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reminders.util import get_two_way_number_for_recipient
from corehq.apps.sms.api import incoming
from corehq.apps.users.models import CommCareUser
from corehq.util.translation import localize
from corehq.util.test_utils import flag_enabled
from custom.ilsgateway.models import (
    DeliveryGroups, SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
)
from custom.ilsgateway.tanzania.reminders import (
    EMG_ERROR, EMG_HELP,
    CONTACT_SUPERVISOR, DELIVERED_CONFIRM, DELIVERY_CONFIRM_CHILDREN,
    DELIVERY_CONFIRM_DISTRICT, DELIVERY_LATE_DISTRICT, DELIVERY_PARTIAL_CONFIRM,
    DELIVERY_REMINDER_DISTRICT, DELIVERY_REMINDER_FACILITY, HELP_REGISTERED,
    INVALID_PRODUCT_CODE, LANGUAGE_CONFIRM, LANGUAGE_UNKNOWN, LOSS_ADJUST_CONFIRM,
    LOSS_ADJUST_HELP, LOSS_ADJUST_NO_SOH, NOT_DELIVERED_CONFIRM, NOT_SUBMITTED_CONFIRM,
    REGISTER_HELP, REGISTER_UNKNOWN_CODE, REGISTER_UNKNOWN_DISTRICT, REGISTRATION_CONFIRM,
    REGISTRATION_CONFIRM_DISTRICT, SOH_CONFIRM, SOH_HELP_MESSAGE,
    STOP_CONFIRM,
    TEST_HANDLER_BAD_CODE, TEST_HANDLER_CONFIRM, TEST_HANDLER_HELP,
)
from custom.ilsgateway.tests.handlers.utils import TEST_DOMAIN, ILSTestScript
from custom.ilsgateway.utils import get_sql_locations_by_domain_and_group
from custom.ilsgateway.tests.utils import bootstrap_user
from custom.zipline.models import EmergencyOrder
import six


class TestHandlers(ILSTestScript):

    def tearDown(self):
        StockReport.objects.all().delete()
        StockState.objects.all().delete()
        EmergencyOrder.objects.all().delete()
        super(TestHandlers, self).tearDown()

    def test_register_facility(self):
        with localize('sw'):
            response = six.text_type(REGISTRATION_CONFIRM)

        script = """
          5551234 > sajili Test Test d31049
          5551234 < %(registration_confirm)s
        """ % {
            "registration_confirm": response % {
                "sdp_name": self.facility3.name,
                "msd_code": "d31049",
                "contact_name": "Test Test"
            }
        }
        self.run_script(script)
        user = CommCareUser.get_by_username('stella')
        self.assertEqual(user.location.site_code, 'd31049')
        self.assertEqual(user.full_name, 'Test Test')

    def test_register_facility_with_unknown_code(self):
        with localize('sw'):
            response = six.text_type(REGISTER_UNKNOWN_CODE)

        script = """
          5551234 > sajili Test Test d00000
          5551234 < %(unknown_code)s
        """ % {
            "unknown_code": response % {
                "msd_code": "d00000",
            }
        }
        self.run_script(script)

    def test_register_district_lowercase(self):
        with localize('sw'):
            response = six.text_type(REGISTRATION_CONFIRM_DISTRICT)

        script = """
          5551234 > sajili Test Test : testdistrict
          5551234 < %(registration_confirm)s
        """ % {
            "registration_confirm": response % {
                "sdp_name": self.district3.name,
                "contact_name": "Test Test"
            }
        }
        self.run_script(script)

        self.assertEqual(CommCareUser.get_by_username('stella').location.site_code, 'd10102')

    def test_register_district_uppercase(self):
        with localize('sw'):
            response = six.text_type(REGISTRATION_CONFIRM_DISTRICT)

        script = """
          5551234 > sajili Test Test : TESTDISTRICT
          5551234 < %(registration_confirm)s
        """ % {
            "registration_confirm": response % {
                "sdp_name": self.district3.name,
                "contact_name": "Test Test"
            }
        }
        self.run_script(script)

        self.assertEqual(CommCareUser.get_by_username('stella').location.site_code, 'd10102')

    def test_register_district_mixed_case(self):
        with localize('sw'):
            response = six.text_type(REGISTRATION_CONFIRM_DISTRICT)

        script = """
          5551234 > sajili Test Test : TESTDISTRICT
          5551234 < %(registration_confirm)s
        """ % {
            "registration_confirm": response % {
                "sdp_name": self.district3.name,
                "contact_name": "Test Test"
            }
        }
        self.run_script(script)

        self.assertEqual(CommCareUser.get_by_username('stella').location.site_code, 'd10102')

    def test_register_district_multiple_word(self):
        with localize('sw'):
            response = six.text_type(REGISTRATION_CONFIRM_DISTRICT)

        script = """
          5551234 > sajili Test Test : Test District 1
          5551234 < %(registration_confirm)s
        """ % {
            "registration_confirm": response % {
                "sdp_name": self.district.name,
                "contact_name": "Test Test"
            }
        }
        self.run_script(script)

        self.assertEqual(CommCareUser.get_by_username('stella').location.site_code, 'dis1')

    def test_register_district_multiple_word_does_not_exist(self):
        with localize('sw'):
            response = six.text_type(REGISTER_UNKNOWN_DISTRICT)

        script = """
          5551234 > sajili Test Test : Test District 1213
          5551234 < %(unknown)s
        """ % {
            "unknown": response % {
                "name": 'Test District 1213'
            }
        }
        self.run_script(script)

    def test_register_district_forgot_separator(self):
        with localize('sw'):
            response = six.text_type(REGISTER_HELP)

        script = """
          5551234 > sajili Test Test testdistrict
          5551234 < %(register_help)s
        """ % {
            "register_help": response
        }
        self.run_script(script)

    def test_register_district_forgot_code(self):
        with localize('sw'):
            response = six.text_type(REGISTER_HELP)

        script = """
          5551234 > sajili Test Test
          5551234 < %(register_help)s
        """ % {
            "register_help": response
        }
        self.run_script(script)

    def test_register_district_mixed_spacing_for_separator(self):
        with localize('sw'):
            response = six.text_type(REGISTRATION_CONFIRM_DISTRICT)

        script = """
          5551234 > sajili Test Test: testdistrict
          5551234 < %(registration_confirm)s
        """ % {
            "registration_confirm": response % {
                "sdp_name": self.district3.name,
                "contact_name": "Test Test"
            }
        }
        self.run_script(script)

        script = """
          5551234 > sajili Test Test :testdistrict
          5551234 < %(registration_confirm)s
        """ % {
            "registration_confirm": response % {
                "sdp_name": self.district3.name,
                "contact_name": "Test Test"
            }
        }
        self.run_script(script)

        script = """
          5551234 > sajili Test Test  :   testdistrict
          5551234 < %(registration_confirm)s
        """ % {
            "registration_confirm": response % {
                "sdp_name": self.district3.name,
                "contact_name": "Test Test"
            }
        }
        self.run_script(script)

    def test_help_registered(self):
        with localize('sw'):
            response = six.text_type(HELP_REGISTERED)

        script = """
          5551234 > msaada
          5551234 < %(help_registered)s
        """ % {'help_registered': response}
        self.run_script(script)

        script = """
          5555678 > help
          5555678 < %(help_registered)s
        """ % {'help_registered': response}
        self.run_script(script)

    def test_not_recognized_keyword(self):
        with localize('sw'):
            response = six.text_type(CONTACT_SUPERVISOR)
        self.run_script(
            """
                5551234 > asdsdasdassd
                5551234 < {0}
            """.format(response)
        )

    def test_delivery_group_basic(self):
        submitting_group = DeliveryGroups().current_submitting_group()
        original_submitting = len(list(get_sql_locations_by_domain_and_group(
            TEST_DOMAIN,
            submitting_group
        )))

        for location in SQLLocation.objects.filter(domain=TEST_DOMAIN):
            if location.metadata.get('group') != submitting_group:
                location.metadata['group'] = submitting_group
                location.save()
                break

        new_submitting = len(list(get_sql_locations_by_domain_and_group(
            TEST_DOMAIN,
            submitting_group
        )))
        self.assertEqual(original_submitting + 1, new_submitting)

    def test_losses_adjustments_without_soh(self):
        with localize('sw'):
            response = six.text_type(LOSS_ADJUST_NO_SOH)
        script = """
            5551234 > um ID -3 dp -5 IP 13
            5551234 < {0}
        """.format(response % {'products_list': 'dp, id, ip'})
        self.run_script(script)

    def test_losses_adjustments(self):
        with localize('sw'):
            response1 = six.text_type(SOH_CONFIRM)
            response2 = six.text_type(LOSS_ADJUST_CONFIRM)

        sohs = {
            'id': 400,
            'dp': 569,
            'ip': 678
        }
        script = """
            5551234 > Hmk Id 400 Dp 569 Ip 678
            5551234 < {0}
        """.format(response1)
        self.run_script(script)

        self.assertEqual(StockState.objects.filter(case_id=self.facility_sp_id).count(), 3)
        for ps in StockState.objects.all():
            self.assertEqual(self.user_fac1.location.linked_supply_point().get_id, ps.case_id)
            self.assertEqual(ps.stock_on_hand, sohs[ps.sql_product.code])

        script = """
            5551234 > um ID -3 dp -5 IP 13
            5551234 < {0}
        """.format(response2)
        self.run_script(script)

        self.assertEqual(StockState.objects.filter(case_id=self.facility_sp_id).count(), 3)

        self.assertEqual(StockState.objects.get(sql_product__code="id").stock_on_hand, 397)
        self.assertEqual(
            StockState.objects.get(sql_product__code="dp", case_id=self.facility_sp_id).stock_on_hand,
            564
        )
        self.assertEqual(StockState.objects.get(sql_product__code="ip").stock_on_hand, 691)

    def test_losses_adjustments_la_word(self):
        with localize('sw'):
            response1 = six.text_type(SOH_CONFIRM)
            response2 = six.text_type(LOSS_ADJUST_CONFIRM)

        sohs = {
            'id': 400,
            'dp': 569,
            'ip': 678
        }

        script = """
            5551234 > Hmk Id 400 Dp 569 Ip 678
            5551234 < {0}
        """.format(response1)
        self.run_script(script)

        self.assertEqual(StockState.objects.filter(case_id=self.facility_sp_id).count(), 3)
        for ps in StockState.objects.all():
            self.assertEqual(self.user_fac1.location.linked_supply_point().get_id, ps.case_id)
            self.assertEqual(ps.stock_on_hand, sohs[ps.sql_product.code])

        script = """
            5551234 > la id -3 dp -5 ip 13
            5551234 < {0}
        """.format(response2)
        self.run_script(script)

        self.assertEqual(StockState.objects.filter(case_id=self.facility_sp_id).count(), 3)

        self.assertEqual(StockState.objects.get(sql_product__code="id").stock_on_hand, 397)
        self.assertEqual(StockState.objects.get(sql_product__code="dp").stock_on_hand, 564)
        self.assertEqual(StockState.objects.get(sql_product__code="ip").stock_on_hand, 691)

    def test_stop(self):
        user = bootstrap_user(
            self.loc1, username='stop_person', domain=self.domain.name,
            phone_number='643', first_name='stop', last_name='Person', language='sw'
        )
        self.addCleanup(user.delete)

        with localize('sw'):
            response = six.text_type(STOP_CONFIRM)

        script = """
          643 > stop
          643 < {0}
        """.format(response)
        self.run_script(script)
        contact = CommCareUser.get_by_username('stop_person')
        self.assertFalse(contact.is_active)

    def test_product_aliases(self):
        with localize('sw'):
            response = six.text_type(SOH_CONFIRM)

        script = """
            5551234 > Hmk iucd 400
            5551234 < {}
        """.format(response)
        self.run_script(script)

        script = """
            5551234 > Hmk Depo 569
            5551234 < {}
        """.format(response)
        self.run_script(script)

        script = """
            5551234 > Hmk IMPL 678
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": response}
        self.run_script(script)

    def test_stock_on_hand_delimiter_standard(self):
        with localize('sw'):
            response = six.text_type(SOH_CONFIRM)

        # standard spacing
        script = """
            5551234 > hmk fs100 md100 ff100 dx100 bp100 pc100 qi100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": response}
        self.run_script(script)

    def test_stock_on_hand_delimiter_no_spaces(self):
        with localize('sw'):
            response = six.text_type(SOH_CONFIRM)

        # no spaces
        script = """
            5551234 > hmk fs100md100ff100dx100bp100pc100qi100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": six.text_type(response)}
        self.run_script(script)

    def test_stock_on_hand_delimiters_mixed_spacing(self):
        with localize('sw'):
            response = six.text_type(SOH_CONFIRM)
        # no spaces
        script = """
            5551234 > hmk fs100 md 100 ff100 dx  100bp   100 pc100 qi100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": six.text_type(response)}
        self.run_script(script)

    def test_stock_on_hand_delimiters_all_spaced_out(self):
        with localize('sw'):
            response = six.text_type(SOH_CONFIRM)
        # all space delimited
        script = """
            5551234 > hmk fs 100 md 100 ff 100 dx 100 bp 100 pc 100 qi 100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": response}
        self.run_script(script)

    def test_stock_on_hand_delimiters_commas(self):
        with localize('sw'):
            response = six.text_type(SOH_CONFIRM)

        # commas
        script = """
            5551234 > hmk fs100,md100,ff100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": response}
        self.run_script(script)

    def test_stock_on_hand_delimiters_commas_and_spaces(self):
        with localize('sw'):
            response = six.text_type(SOH_CONFIRM)

        # commas
        script = """
            5551234 > hmk fs100, md100, ff100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": response}
        self.run_script(script)

    def test_stock_on_hand_delimiters_extra_spaces(self):
        with localize('sw'):
            response = six.text_type(SOH_CONFIRM)

        # extra spaces
        script = """
            5551234 > hmk fs  100   md    100     ff      100       pc        100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": response}
        self.run_script(script)

    def test_stock_on_hand_mixed_delimiters_and_spacing(self):
        with localize('sw'):
            response = six.text_type(SOH_CONFIRM)

        # mixed - commas, spacing
        script = """
            5551234 > hmk fs100 , md100,ff 100 pc  100  qi,       1000,bp, 100, dx,100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": response}
        self.run_script(script)

    def test_stock_on_hand_language_swahili(self):
        with localize('sw'):
            response = six.text_type(SOH_CONFIRM)
        script = """
            5551234 > hmk fs100md100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": response}
        self.run_script(script)

    def test_stock_on_hand_language_english(self):
        with localize('en'):
            response = six.text_type(LANGUAGE_CONFIRM)
            response2 = six.text_type(SOH_CONFIRM)

        language_message = """
            5551234 > language en
            5551234 < {0}
        """.format(six.text_type(response % dict(language='English')))
        self.run_script(language_message)

        script = """
            5551234 > hmk fs100md100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": response2}
        self.run_script(script)

        with localize('sw'):
            response = six.text_type(LANGUAGE_CONFIRM)

        language_message = """
            5551234 > language sw
            5551234 < {0}
        """.format(six.text_type(response % dict(language='Swahili')))
        self.run_script(language_message)

    def test_multiline_message(self):
        quantities = {
            'fs': 100,
            'md': 100,
            'ff': 100,
            'pc': 100
        }
        message = """
            hmk
            fs 100 md 100 ff 100 pc 100
        """
        verified_number = get_two_way_number_for_recipient(self.user1)
        msg = incoming(
            verified_number.phone_number, message, verified_number.backend_id
        )
        self.assertIsNotNone(msg)

        stock_states = StockState.objects.filter(
            case_id=self.facility_sp_id
        ).values_list('sql_product__code', 'stock_on_hand')

        for product_code, quantity in stock_states:
            self.assertEqual(quantity, quantities[product_code])

    def _verify_language(self, language, phone_number):
        previous_language = translation.get_language()
        translation.activate(language)
        expected = six.text_type(HELP_REGISTERED)
        translation.activate(previous_language)
        script = """
          %(phone)s > help
          %(phone)s < %(help_registered)s
        """ % {'phone': phone_number, 'help_registered': expected}
        self.run_script(script)

    def test_language_english(self):
        with localize('en'):
            response = six.text_type(LANGUAGE_CONFIRM)
        script = """
            5551234 > language en
            5551234 < %(language_confirm)s
            """ % {'language_confirm': response % {"language": "English"}}
        self.run_script(script)
        self._verify_language('en', '5551234')

    def test_language_swahili(self):
        with localize('sw'):
            response = six.text_type(LANGUAGE_CONFIRM)
        script = """
            5551234 > lugha sw
            5551234 < %(language_confirm)s
            """ % {'language_confirm': response % {"language": "Swahili"}}
        self.run_script(script)
        self._verify_language('sw', '5551234')

    def test_language_unknown(self):
        with localize('sw'):
            response = six.text_type(LANGUAGE_UNKNOWN)
        script = """
            5551234 > language de
            5551234 < %(language_unknown)s
            """ % {'language_unknown': response % {"language": "de"}}
        self.run_script(script)

    def test_randr_not_submitted(self):
        with localize('sw'):
            response = six.text_type(NOT_SUBMITTED_CONFIRM)

        script = """
          5551234 > sijatuma
          5551234 < {0}
        """.format(response)
        self.run_script(script)

        sps = SupplyPointStatus.objects.filter(location_id=self.loc1.get_id,
                                               status_type="rr_fac").order_by("-status_date")[0]

        self.assertEqual(SupplyPointStatusValues.NOT_SUBMITTED, sps.status_value)
        self.assertEqual(SupplyPointStatusTypes.R_AND_R_FACILITY, sps.status_type)

    def test_delivery_facility_received_no_quantities_reported(self):
        with localize('sw'):
            response = six.text_type(DELIVERY_PARTIAL_CONFIRM)
        script = """
            5551234 > nimepokea
            5551234 < {0}
        """.format(response)
        self.run_script(script)

        sps = SupplyPointStatus.objects.filter(location_id=self.loc1.get_id,
                                               status_type="del_fac").order_by("-status_date")[0]

        self.assertEqual(SupplyPointStatusValues.RECEIVED, sps.status_value)
        self.assertEqual(SupplyPointStatusTypes.DELIVERY_FACILITY, sps.status_type)

    def test_delivery_facility_received_quantities_reported(self):
        with localize('sw'):
            response = six.text_type(DELIVERED_CONFIRM)

        sohs = {
            'jd': 400,
            'mc': 569
        }
        script = """
            5551234 > delivered jd 400 mc 569
            5551234 < {0}
            """.format(response % {'reply_list': 'jd 400, mc 569'})
        self.run_script(script)
        self.assertEqual(2, StockState.objects.count())
        for ps in StockState.objects.all().order_by('pk'):
            self.assertEqual(self.loc1.linked_supply_point().get_id, ps.case_id)
            self.assertEqual(ps.stock_on_hand, sohs[ps.sql_product.code])

    def test_delivery_facility_not_received(self):
        with localize('sw'):
            response = six.text_type(NOT_DELIVERED_CONFIRM)

        script = """
            5551234 > sijapokea
            5551234 < {0}
            """.format(response)
        self.run_script(script)

        sps = SupplyPointStatus.objects.filter(location_id=self.loc1.get_id,
                                               status_type="del_fac").order_by("-status_date")[0]

        self.assertEqual(SupplyPointStatusValues.NOT_RECEIVED, sps.status_value)
        self.assertEqual(SupplyPointStatusTypes.DELIVERY_FACILITY, sps.status_type)

    def test_delivery_facility_report_product_error(self):
        with localize('sw'):
            response = six.text_type(INVALID_PRODUCT_CODE)
        script = """
            5551234 > nimepokea Ig 400 Dp 569 Ip 678
            5551234 < %(error_message)s
            """ % {'error_message': response % {"product_code": "ig"}}
        self.run_script(script)

    def test_delivery_district_received(self):
        with localize('sw'):
            response = six.text_type(DELIVERY_CONFIRM_DISTRICT)
            response2 = six.text_type(DELIVERY_CONFIRM_CHILDREN)
        script = """
          555 > nimepokea
          555 < {0}
          5551234 < {1}
          5555678 < {1}
        """.format(
            response % dict(contact_name="{0} {1}".format(
                self.user_dis.first_name,
                self.user_dis.last_name
            ), facility_name=self.dis.name),
            response2 % dict(district_name=self.dis.name)
        )

        self.run_script(script)

        sps = SupplyPointStatus.objects.filter(location_id=self.dis.get_id,
                                               status_type="del_dist").order_by("-status_date")[0]

        self.assertEqual(SupplyPointStatusValues.RECEIVED, sps.status_value)
        self.assertEqual(SupplyPointStatusTypes.DELIVERY_DISTRICT, sps.status_type)

    def test_delivery_district_not_received(self):
        with localize('sw'):
            response = six.text_type(NOT_DELIVERED_CONFIRM)

        script = """
          555 > sijapokea
          555 < {0}
        """.format(response)
        self.run_script(script)

        sps = SupplyPointStatus.objects.filter(location_id=self.dis.get_id,
                                               status_type="del_dist").order_by("-status_date")[0]

        self.assertEqual(SupplyPointStatusValues.NOT_RECEIVED, sps.status_value)
        self.assertEqual(SupplyPointStatusTypes.DELIVERY_DISTRICT, sps.status_type)

    def test_message_initiator_help(self):
        with localize('sw'):
            response = six.text_type(TEST_HANDLER_HELP)
        script = """
            5551234 > test
            5551234 < %s
        """ % response
        self.run_script(script)

    def test_message_initiator_losses_adjustments(self):
        with localize('sw'):
            response1 = six.text_type(TEST_HANDLER_CONFIRM)
            response2 = six.text_type(LOSS_ADJUST_HELP)
        script = """
            5551234 > test la d31049
            5551234 < %(test_handler_confirm)s
            32347 < %(response)s
            32348 < %(response)s
            32349 < %(response)s
            """ % {
            "test_handler_confirm": response1,
            "response": response2
        }
        self.run_script(script)
        supply_point_status = SupplyPointStatus.objects.filter(
            location_id=self.facility3.get_id,
            status_type=SupplyPointStatusTypes.LOSS_ADJUSTMENT_FACILITY
        ).order_by("-status_date")[0]
        self.assertEqual(SupplyPointStatusValues.REMINDER_SENT, supply_point_status.status_value)
        self.assertEqual(SupplyPointStatusTypes.LOSS_ADJUSTMENT_FACILITY, supply_point_status.status_type)

    def test_message_initiator_fw(self):
        with localize('sw'):
            response = six.text_type(TEST_HANDLER_CONFIRM)
        script = """
            5551234 > test fw D31049 %(test_message)s
            5551234 < %(test_handler_confirm)s
            32347 < %(test_message)s
            32348 < %(test_message)s
            32349 < %(test_message)s
            """ % {"test_handler_confirm": response,
                   "test_message": "this is a test message"}
        self.run_script(script)

    def test_message_initiator_bad_code(self):
        with localize('sw'):
            response = six.text_type(TEST_HANDLER_BAD_CODE)
        script = """
            5551234 > test la d5000000
            5551234 < %(test_bad_code)s
            """ % {"test_bad_code": response % {"code": "d5000000"}}
        self.run_script(script)

    def test_message_initiator_delivery_facility(self):
        with localize('sw'):
            response1 = six.text_type(TEST_HANDLER_CONFIRM)
            response2 = six.text_type(DELIVERY_REMINDER_FACILITY)
        script = """
            5551234 > test delivery d31049
            5551234 < %(test_handler_confirm)s
            32347 < %(response)s
            32348 < %(response)s
            32349 < %(response)s
            """ % {
            "test_handler_confirm": response1,
            "response": response2
        }
        self.run_script(script)
        supply_point_status = SupplyPointStatus.objects.filter(
            location_id=self.facility3.get_id,
            status_type=SupplyPointStatusTypes.DELIVERY_FACILITY
        ).order_by("-status_date")[0]
        self.assertEqual(SupplyPointStatusValues.REMINDER_SENT, supply_point_status.status_value)
        self.assertEqual(SupplyPointStatusTypes.DELIVERY_FACILITY, supply_point_status.status_type)

    def test_message_initiator_delivery_district(self):
        with localize('sw'):
            response1 = six.text_type(TEST_HANDLER_CONFIRM)
            response2 = six.text_type(DELIVERY_REMINDER_DISTRICT)
        script = """
            5551234 > test delivery d10101
            5551234 < %(test_handler_confirm)s
            32350 < %(response)s
            32351 < %(response)s
            32352 < %(response)s
            """ % {
            "test_handler_confirm": response1,
            "response": response2
        }
        self.run_script(script)
        supply_point_status = SupplyPointStatus.objects.filter(
            location_id=self.district2.get_id,
            status_type=SupplyPointStatusTypes.DELIVERY_DISTRICT
        ).order_by("-status_date")[0]
        self.assertEqual(SupplyPointStatusValues.REMINDER_SENT, supply_point_status.status_value)
        self.assertEqual(SupplyPointStatusTypes.DELIVERY_DISTRICT, supply_point_status.status_type)

    def test_message_initiator_late_delivery_report_district(self):
        with localize('sw'):
            response1 = six.text_type(TEST_HANDLER_CONFIRM)
            response2 = six.text_type(DELIVERY_LATE_DISTRICT)
        script = """
            5551234 > test latedelivery d10101
            5551234 < %(test_handler_confirm)s
            32350 < %(response)s
            32351 < %(response)s
            32352 < %(response)s
            """ % {
            "test_handler_confirm": response1,
            "response": six.text_type(response2 % {
                'group_name': 'changeme',
                'group_total': 1,
                'not_responded_count': 2,
                'not_received_count': 3
            })
        }
        self.run_script(script)

    def test_message_initiator_soh(self):
        with localize('sw'):
            response1 = six.text_type(TEST_HANDLER_CONFIRM)
            response2 = six.text_type(SOH_HELP_MESSAGE)
        script = """
            5551234 > test soh d31049
            5551234 < %(test_handler_confirm)s
            32347 < %(response)s
            32348 < %(response)s
            32349 < %(response)s
            5551234 > test hmk d31049
            5551234 < %(test_handler_confirm)s
            32347 < %(response)s
            32348 < %(response)s
            32349 < %(response)s
            """ % {
            "test_handler_confirm": response1,
            "response": response2
        }
        self.run_script(script)
        supply_point_status = SupplyPointStatus.objects.filter(
            location_id=self.facility3.get_id,
            status_type=SupplyPointStatusTypes.SOH_FACILITY
        ).order_by("-status_date")[0]
        self.assertEqual(SupplyPointStatusValues.REMINDER_SENT, supply_point_status.status_value)
        self.assertEqual(SupplyPointStatusTypes.SOH_FACILITY, supply_point_status.status_type)

    def testTrans(self):
        with localize('sw'):
            response = six.text_type(SOH_CONFIRM)

        script = """
          5551234 > trans yes
          5551234 < %s
        """ % response
        self.run_script(script)

        script = """
          5551234 > trans no
          5551234 < %s
        """ % response
        self.run_script(script)

        self.assertEqual(SupplyPointStatus.objects.count(), 2)
        status1 = SupplyPointStatus.objects.get(status_type=SupplyPointStatusTypes.TRANS_FACILITY,
                                                status_value=SupplyPointStatusValues.NOT_SUBMITTED)
        status2 = SupplyPointStatus.objects.get(status_type=SupplyPointStatusTypes.TRANS_FACILITY,
                                                status_value=SupplyPointStatusValues.SUBMITTED)
        self.assertEqual(self.user1.location_id, status1.location_id)
        self.assertEqual(self.user1.location_id, status2.location_id)

    def test_soh(self):
        with localize('sw'):
            response1 = six.text_type(SOH_CONFIRM)
        script = """
            5551234 > soh jd 400 mc 569
            5551234 < {0}
        """.format(response1)
        self.run_script(script)

        self.run_script(script)
        self.assertEqual(2, StockState.objects.count())
        for ps in StockState.objects.all():
            self.assertEqual(self.user_fac1.location.linked_supply_point().get_id, ps.case_id)
            self.assertTrue(0 != ps.stock_on_hand)

    def test_soh_in_swahili(self):
        with localize('sw'):
            response1 = six.text_type(LANGUAGE_CONFIRM)
            response2 = six.text_type(SOH_CONFIRM)

        language_message = """
            5551235 > language sw
            5551235 < {0}
        """.format(response1 % dict(language='Swahili'))
        self.run_script(language_message)

        soh_script = """
            5551235 > hmk jd 400 mc 569
            5551235 < {0}
        """.format(response2)
        self.run_script(soh_script)

    @flag_enabled('EMG_AND_REC_SMS_HANDLERS')
    def test_help(self):
        script = """
            5551234 > emg
            5551234 < {}
        """.format(six.text_type(EMG_HELP))
        self.run_script(script)

    @flag_enabled('EMG_AND_REC_SMS_HANDLERS')
    def test_valid_message(self):
        script = """
            5551235 > emg dp 100 fs 50
        """
        self.run_script(script)

        emergency_order = EmergencyOrder.objects.filter(domain=self.domain.name)[0]

        self.assertListEqual(
            [
                emergency_order.domain,
                emergency_order.requesting_user_id,
                emergency_order.requesting_phone_number,
                emergency_order.location_code,
                emergency_order.products_requested
            ],
            [
                self.domain.name,
                self.en_user1.get_id,
                '5551235',
                self.en_user1.sql_location.site_code,
                {'dp': {'quantity': '100'}, 'fs': {'quantity': '50'}}
            ]
        )

    @flag_enabled('EMG_AND_REC_SMS_HANDLERS')
    def test_invalid_quantity(self):
        script = """
            5551234 > emg dp quantity fs 50
            5551234 < {}
        """.format(six.text_type(EMG_ERROR))
        self.run_script(script)

    @flag_enabled('EMG_AND_REC_SMS_HANDLERS')
    def test_incomplete_message(self):
        script = """
            5551234 > emg dp fs 50
            5551234 < {}
        """.format(six.text_type(EMG_ERROR))
        self.run_script(script)

    @flag_enabled('EMG_AND_REC_SMS_HANDLERS')
    def test_invalid_product_code(self):
        script = """
            5551234 > emg invalid_code 40 fs 50
            5551234 < {}
        """.format(six.text_type(INVALID_PRODUCT_CODE % {'product_code': 'invalid_code'}))
        self.run_script(script)

    def test_unicode_characters(self):
        with localize('sw'):
            response = _(SOH_CONFIRM)
        script = """
            5551235 > Hmk Id 400 \u0660Dp 569 Ip 678
            5551235 < %(soh_confirm)s
        """ % {"soh_confirm": response}

        now = datetime.datetime.utcnow()
        self.run_script(script)

        txs = list(StockTransaction.objects.filter(
            case_id=self.loc1.sql_location.supply_point_id,
            report__date__gte=now)
        )
        self.assertEqual(len(txs), 3)

        self.assertSetEqual(
            {(tx.sql_product.code, int(tx.stock_on_hand)) for tx in txs},
            {('id', 400), ('dp', 569), ('ip', 678)}
        )
