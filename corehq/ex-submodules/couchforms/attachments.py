from corehq.util.couch_helpers import CouchAttachmentsBuilder


class AttachmentsManager(object):

    def __init__(self, xform):
        self.xform = xform
        self.builder = CouchAttachmentsBuilder()

    def store_attachment(self, name, content, content_type=None):
        self.builder.add(
            content=content,
            name=name,
            content_type=content_type,
        )

    def commit(self):
        self.xform._attachments = self.builder.to_json()
