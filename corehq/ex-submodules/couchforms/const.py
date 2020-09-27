
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
# Copied from https://github.com/dimagi/commcare-android/blob/62ae0bde9ed623db17bcc44ad678d693e0b73cb6/app/src/org/commcare/utils/FormUploadUtil.java#L57
SUPPORTED_MEDIA_FILE_EXTENSIONS = [
    "jpg", "jpeg", "3gpp", "3gp", "3ga", "3g2", "mp3", "wav", "amr",
    "mp4", "3gp2", "mpg4", "mpeg4", "m4v", "mpg", "mpeg", "qcp", "ogg"
]
PERMITTED_FORM_SUBMISSION_FILE_EXTENSIONS = ['xml']
