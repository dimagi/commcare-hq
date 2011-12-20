from tastypie.bundle import Bundle
from tastypie.resources import Resource


class CouchdbkitResource(Resource):
    """
    Helper class for making Couchdbkit Backed resources for tastypie.

    In making your Resources, subclass this instead of the default TastyPie Resource.

    In your Resource's Meta class, the new things to add are:
    view_name, the string for the view you want to call for your resource
    doc_class, the couchdbkit class you want to use as part of your serialization.

    Note: This assumes you want to use a CouchdbKit backed Document class, if you need to just use pure json from couch,
    or call reduced views, then you'll need to adjust how the deserialization works.
    """
    def _db(self):
        """
        Using the doc_class, get the underlying db.
        """
        return self._meta.doc_class.get_db()

    def _doctype(self):
        """
        Helper function for returning the doc_type in the meta class
        """
        return self._meta.doc_class

    def get_resource_uri(self, bundle_or_obj):
        """
        URI based upon _id of the document.
        """
        kwargs = {
            'resource_name': self._meta.resource_name,
            }

        if isinstance(bundle_or_obj, Bundle):
            kwargs['pk'] = bundle_or_obj.obj['_id']
        else:
            kwargs['pk'] = bundle_or_obj['_id']

        if self._meta.api_name is not None:
            kwargs['api_name'] = self._meta.api_name

        return self._build_reverse_url("api_dispatch_detail", kwargs=kwargs)

    def get_object_list(self, request):
        """
        Assumes that the document type and the view correspond
        """
        results = self._meta.doc_class.view(self._meta.view_name, include_docs=True).all()
        return [x for x in results]

    def obj_get_list(self, request=None, **kwargs):
        #no filtering
        return self.get_object_list(request)

    def obj_get(self, request=None, **kwargs):
        """
        Assume a fully formed couchdbkit document.
        """
        document = self._doctype().get(kwargs['pk'])
        return document


    #not implemented yet are the create/update/delete
    def obj_create(self, bundle, request=None, **kwargs):
        pass

    def obj_update(self, bundle, request=None, **kwargs):
        pass

    def obj_delete_list(self, request=None, **kwargs):
        pass

    def obj_delete(self, request=None, **kwargs):
        pass

    def rollback(self, bundles):
        pass