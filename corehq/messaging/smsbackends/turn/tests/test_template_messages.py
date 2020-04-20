from django.test import SimpleTestCase

from corehq.messaging.smsbackends.turn.models import (
    get_template_hsm_parts,
    is_whatsapp_template_message,
)


class TurnWhatsAppTemplateTest(SimpleTestCase):

    def test_is_whatsapp_template(self):
        """cc_wa_template:template_name:lang_code:{var1}{var2}{var3}
        """
        sample_message = "cc_wa_template:template_name:en-US:{name}{address}"
        self.assertTrue(is_whatsapp_template_message(sample_message))
        self.assertFalse(is_whatsapp_template_message("Hello Farid your coffee is ready."))

    def test_parse_template_parts(self):
        parts = get_template_hsm_parts(
            "cc_wa_template:template_name:en-US:{name of person}   {address  }"
        )
        self.assertEqual(parts.template_name, "template_name")
        self.assertEqual(parts.lang_code, "en-US")
        self.assertEqual(parts.params, ["name of person", "address  "])

        # extra stuff at the end, this is added in by formplayer when parsing SMS forms
        parts = get_template_hsm_parts(
            "cc_wa_template:template_name:en-US:{name of person, Snoopy},{address}1:yes, 2:no"
        )
        self.assertEqual(parts.template_name, "template_name")
        self.assertEqual(parts.lang_code, "en-US")
        self.assertEqual(parts.params, ["name of person, Snoopy", "address"])

        # no params
        parts = get_template_hsm_parts("cc_wa_template:template_name:en-US")
        self.assertEqual(parts.template_name, "template_name")
        self.assertEqual(parts.lang_code, "en-US")
        self.assertEqual(parts.params, [])
