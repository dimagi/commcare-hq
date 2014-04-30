# Stub models file
from couchdbkit.ext.django.schema import Document, StringProperty


class SonositeUpload(Document):
    study_id = StringProperty()
    case_id = StringProperty
