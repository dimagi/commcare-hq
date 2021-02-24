import re
from collections import namedtuple
from corehq.apps.domain.models import Domain
from dimagi.utils.web import get_url_base

WA_TEMPLATE_STRING = "cc_wa_template"


class WhatsAppTemplateStringException(Exception):
    pass


def is_whatsapp_template_message(message_text):
    return WA_TEMPLATE_STRING in message_text.lower()


def is_multimedia_message(msg):
    return 'caption_image' in msg.custom_metadata\
           or 'caption_audio' in msg.custom_metadata\
           or 'caption_video' in msg.custom_metadata


def get_multimedia_urls(msg):
    image_url = audio_url = video_url = None
    domain_obj = Domain.get_by_name(msg.domain, strict=True)
    for app in domain_obj.full_applications():
        for path, media in app.get_media_objects(remove_unused=True):
            if 'caption_image' in msg.custom_metadata and msg.custom_metadata['caption_image'] == path:
                image_url = get_url_base() + media.url() + 'image.png'
            if 'caption_audio' in msg.custom_metadata and msg.custom_metadata['caption_audio'] == path:
                audio_url = get_url_base() + media.url() + 'audio.mp3'
            if 'caption_video' in msg.custom_metadata and msg.custom_metadata['caption_video'] == path:
                video_url = get_url_base() + media.url() + 'video.mp4'
    return image_url, audio_url, video_url


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
