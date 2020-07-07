import re
from collections import namedtuple

WA_TEMPLATE_STRING = "cc_wa_template"


class WhatsAppTemplateStringException(Exception):
    pass


def is_whatsapp_template_message(message_text):
    return WA_TEMPLATE_STRING in message_text.lower()


def extract_error_message_from_template_string(message_text):
    """If message is labeled as "invalid_survey_response" then error message should be
    extracted from template string
    """
    return message_text.split(WA_TEMPLATE_STRING)[0]


def get_template_hsm_parts(message_text):
    """The magic string users enter looks like: cc_wa_template:template_name:lang_code:{var1}{var2}{var3}
    """
    HsmParts = namedtuple("hsm_parts", "template_name lang_code params")
    parts = message_text.split(":")

    try:
        params = re.findall("{(.+?)}+", parts[3])
    except IndexError:
        params = []

    try:
        return HsmParts(template_name=parts[1], lang_code=parts[2], params=params)
    except IndexError:
        raise WhatsAppTemplateStringException
