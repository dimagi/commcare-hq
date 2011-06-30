from couchdbkit.ext.django.schema import Document, IntegerProperty, DictProperty,\
    Property
import json
from dimagi.utils.mixins import UnicodeMixIn


class JsonProperty(Property):
    """
    A property that stores data in an arbitrary JSON object.
    """
    
    def to_python(self, value):
        return json.loads(value)

    def to_json(self, value):
        return json.dumps(value)

class ExportSchema(Document, UnicodeMixIn):
    """
    An export schema that can store intermittent contents of the export so
    that the entire doc list doesn't have to be used to generate the export
    """
    index = JsonProperty()
    seq = IntegerProperty()
    schema = DictProperty()
    
    def __unicode__(self):
        return "%s: %s" % (json.dumps(self.index), self.seq)
    
    @classmethod
    def last(cls, index):
        return cls.view("couchexport/schema_checkpoints", 
                        startkey=[json.dumps(index), {}],
                        endkey=[json.dumps(index)],
                        descending=True, limit=1,
                        include_docs=True).one()
                                 
    