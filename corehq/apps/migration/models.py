from couchdbkit.ext.django.schema import Document, StringProperty

class MigrationUser(Document):
    username = StringProperty()
    user_id = StringProperty()
    domain = StringProperty()
    