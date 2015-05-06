from dimagi.ext.couchdbkit import Document, StringProperty, DateProperty


"""
Two Couch models used to temporarily hold important
information and the attachments from the upload. These
are passed to Celery, but are in a doc so that we don't
lose images if something fails.
"""


class SonositeUpload(Document):
    study_id = StringProperty()
    related_case_id = StringProperty()


class VscanUpload(Document):
    scanner_serial = StringProperty()
    scan_id = StringProperty()
    date = DateProperty()
