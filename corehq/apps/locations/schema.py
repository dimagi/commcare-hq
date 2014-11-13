from couchdbkit.ext.django.schema import (
    StringProperty, BooleanProperty, DocumentSchema, StringListProperty
)


class LocationType(DocumentSchema):
    name = StringProperty()
    code = StringProperty()
    allowed_parents = StringListProperty()
    administrative = BooleanProperty()

    @classmethod
    def wrap(cls, obj):
        from corehq.apps.commtrack.util import unicode_slug
        if not obj.get('code'):
            obj['code'] = unicode_slug(obj['name'])
        return super(LocationType, cls).wrap(obj)
