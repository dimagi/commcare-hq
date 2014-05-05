# Stub models file
from couchdbkit.ext.django.schema import Document, StringProperty, DateProperty


class SonositeUpload(Document):
    study_id = StringProperty()
    related_case_id = StringProperty()


class VscanUpload(Document):
    scanner_serial = StringProperty()
    scan_id = StringProperty()
    date = DateProperty()
