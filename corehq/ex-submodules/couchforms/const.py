
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

# Should be in sync with file extensions supported by CommCare & FP
# https://github.com/dimagi/commcare-android/blob/ef45074bbb8647339387e179a2baca89fb394a23/app/src/org/commcare/utils/FormUploadUtil.java#LL63C1-L63C1
# https://github.com/dimagi/commcare-hq/blob/7bccfe34888f6dc0d3f94e4d3846007b0156c8eb/corehq/apps/cloudcare/static/cloudcare/js/form_entry/entries.js#L914-L918
VALID_ATTACHMENT_FILE_EXTENSIONS = [
    "jpg", "jpeg", "3gpp", "3gp", "3ga", "3g2", "mp3",
    "wav", "amr", "mp4", "3gp2", "mpg4", "mpeg4",
    "m4v", "mpg", "mpeg", "qcp", "ogg",
    # an additional ones added by FP
    # https://github.com/dimagi/formplayer/blob/916c66aec6eb351e1077828415e4a8ee20766802/src/main/java/org/commcare/formplayer/services/MediaValidator.kt#L16-L37
    "png", "pdf"
]
