from __future__ import absolute_import
from __future__ import unicode_literals

import json

from django.contrib.postgres.fields import JSONField
import six


class DocumentField(JSONField):
    def __init__(self, document_class, *args, **kwargs):
        self.document_class = document_class
        super(DocumentField, self).__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super(DocumentField, self).deconstruct()
        kwargs['document_class'] = self.document_class
        return name, path, args, kwargs

    def from_db_value(self, value, expression, connection, context):
        return self.document_class.wrap(value)

    def to_python(self, value):
        if isinstance(value, self.document_class):
            return value

        if isinstance(value, six.string_types):
            value = json.loads(value)

        return self.document_class.wrap(value)

    def get_prep_value(self, value):
        if isinstance(value, self.document_class):
            value = value.to_json()

        return super(DocumentField, self).get_prep_value(value)
