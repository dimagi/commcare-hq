from corehq.apps.users.models import CommCareUser
from corehq.util.translation import localize
from custom.ilsgateway.tanzania.reminders import REGISTRATION_CONFIRM, REGISTER_UNKNOWN_CODE, \
    REGISTRATION_CONFIRM_DISTRICT, REGISTER_UNKNOWN_DISTRICT, REGISTER_HELP
from custom.ilsgateway.tests.handlers.utils import ILSTestScript


class RegisterHandler(ILSTestScript):

    def test_register_facility(self):
        with localize('sw'):
            response = unicode(REGISTRATION_CONFIRM)

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
            response = unicode(REGISTER_UNKNOWN_CODE)

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
            response = unicode(REGISTRATION_CONFIRM_DISTRICT)

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
            response = unicode(REGISTRATION_CONFIRM_DISTRICT)

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
            response = unicode(REGISTRATION_CONFIRM_DISTRICT)

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
            response = unicode(REGISTRATION_CONFIRM_DISTRICT)

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
            response = unicode(REGISTER_UNKNOWN_DISTRICT)

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
            response = unicode(REGISTER_HELP)

        script = """
          5551234 > sajili Test Test testdistrict
          5551234 < %(register_help)s
        """ % {
            "register_help": response
        }
        self.run_script(script)

    def test_register_district_forgot_code(self):
        with localize('sw'):
            response = unicode(REGISTER_HELP)

        script = """
          5551234 > sajili Test Test
          5551234 < %(register_help)s
        """ % {
            "register_help": response
        }
        self.run_script(script)

    def test_register_district_mixed_spacing_for_separator(self):
        with localize('sw'):
            response = unicode(REGISTRATION_CONFIRM_DISTRICT)

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
