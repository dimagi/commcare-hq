from tastypie.resources import Resource


class JsonDefaultResourceMixIn(object):
    """
    Mixin to avoid having to get the "please append format=json to your url"
    message and always default to json.
    """

    def determine_format(self, request):
        return "application/json"

class JsonResource(JsonDefaultResourceMixIn, Resource):
    """
    This can be extended to default to json formatting. 
    """
    # This exists in addition to the mixin since the order of the class
    # definitions actually matters
    
