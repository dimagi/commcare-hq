from dimagi.ext import jsonobject


class ChangeMeta(jsonobject.JsonObject):
    document_id = jsonobject.StringProperty(required=True)
    data_source_type = jsonobject.StringProperty(required=True)
    data_source_name = jsonobject.StringProperty(required=True)
    document_type = jsonobject.StringProperty()
    document_subtype = jsonobject.StringProperty()
    domain = jsonobject.StringProperty()
    is_deletion = jsonobject.BooleanProperty()
    _allow_dynamic_properties = False
