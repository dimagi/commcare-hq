import json

from tastypie.serializers import Serializer


class ListToSingleObjectSerializer(Serializer):
    """
    Serializer class that takes a list of one object and removes the other metadata
    around the list view so that just the object is returned.

    See IdentityResource for an example.
    """

    def to_json(self, data, options=None):
        # note: this is not valid if there is ever not exactly one object returned
        return json.dumps(data['objects'][0].data)
