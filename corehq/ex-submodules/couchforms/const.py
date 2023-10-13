from itertools import chain

TAG_TYPE = "#type"
TAG_XML = "#xml"
TAG_VERSION = "@version"
TAG_UIVERSION = "@uiVersion"
TAG_NAMESPACE = "@xmlns"
TAG_NAME = "@name"

TAG_META = "meta"

TAG_FORM = 'form'

ATTACHMENT_NAME = "form.xml"

MAGIC_PROPERTY = 'xml_submission_file'

RESERVED_WORDS = [TAG_TYPE, TAG_XML, TAG_VERSION, TAG_UIVERSION, TAG_NAMESPACE,
                  TAG_NAME, TAG_META, ATTACHMENT_NAME, 'case', MAGIC_PROPERTY]

DEVICE_LOG_XMLNS = 'http://code.javarosa.org/devicereport'

# Should be in sync with file extensions supported by CommCare
# https://github.com/dimagi/commcare-android/blob/ef45074bbb8647339387e179a2baca89fb394a23/app/src/org/commcare/utils/FormUploadUtil.java#LL63C1-L63C1
VALID_ATTACHMENT_FILE_EXTENSION_MAP = {
    "image/*,.pdf": ["jpg", "jpeg", "png", "pdf"],
    "audio/*": ["3ga", "mp3", "wav", "amr", "qcp", "ogg"],
    "video/*": ["3gpp", "3gp", "3gp2", "3g2", "mp4", "mpg4", "mpeg4", "m4v", "mpg", "mpeg"],
}

VALID_ATTACHMENT_FILE_EXTENSIONS = set(chain.from_iterable(VALID_ATTACHMENT_FILE_EXTENSION_MAP.values()))
