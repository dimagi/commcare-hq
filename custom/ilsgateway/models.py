from couchdbkit.ext.django.schema import DocumentSchema, BooleanProperty, StringProperty
from django.db import models

class ILSGatewayConfig(DocumentSchema):
    enabled = BooleanProperty(default=False)
    url = StringProperty()
    username = StringProperty()
    password = StringProperty()

    @property
    def is_configured(self):
        return True if self.enabled and self.url and self.password and self.username else False


class MigrationCheckpoint(models.Model):
     domain = models.CharField(max_length=100)
     date = models.DateTimeField()