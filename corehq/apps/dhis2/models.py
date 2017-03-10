from dimagi.ext.couchdbkit import Document, StringProperty


class Dhis2Connection(Document):
    domain = StringProperty()
    server_url = StringProperty()
    username = StringProperty()
    password = StringProperty()
