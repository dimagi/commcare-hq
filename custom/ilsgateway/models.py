from couchdbkit.ext.django.schema import DocumentSchema, BooleanProperty, StringProperty


class ILSGatewayConfig(DocumentSchema):
    enabled = BooleanProperty(default=False)
    url = StringProperty()
    username = StringProperty()
    password = StringProperty()

    @property
    def is_configured(self):
        return True if self.enabled and self.url and self.password and self.username else False