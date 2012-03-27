from tastypie.bundle import Bundle
from tastypie.paginator import Paginator
from tastypie.resources import Resource

class CouchdbkitTastyPaginator(Paginator):
    """
    Override of the default Paginator for TastyPie - using couchdbkit, we can limit/paginate using the
    view API, but the slicing assumes we have a queryset, so to be more efficient, we do that in the get_list
    """
    def get_slice(self, limit, offset):
        """
        Since we are assuming that couchdbkit already paginated it, we will return all our objects.
        """
        return self.objects


class DataTablesMixin(object):
    """
    Mixin to override the get_list functionality of get_list to support a datatables output
    """
    def get_list(self, request, **kwargs):
        """
        Returns a serialized list of resources.

        Calls ``obj_get_list`` to provide the data, then handles that result
        set and serializes it.

        Should return a HttpResponse (200 OK).
        """
        # TODO: Uncached for now. Invalidation that works for everyone may be
        #       impossible.
        objects = self.obj_get_list(request=request, **self.remove_api_resource_names(kwargs))
        sorted_objects = self.apply_sorting(objects, options=request.GET)

        paginator = self._meta.paginator_class(request.GET, sorted_objects, resource_uri=self.get_resource_list_uri(), limit=self._meta.limit)
        to_be_serialized = paginator.page()

        # Dehydrate the bundles in preparation for serialization.
        bundles = [self.build_bundle(obj=obj, request=request) for obj in to_be_serialized['objects']]
        to_be_serialized['aaData'] = [self.full_dehydrate(bundle) for bundle in bundles]
        to_be_serialized = self.alter_list_data_to_serialize(request, to_be_serialized)
        return self.create_response(request, to_be_serialized)


class CouchdbkitResource(Resource):
    """
    Helper class for making Couchdbkit Backed resources for tastypie.

    In making your Resources, subclass this instead of the default TastyPie Resource.

    In your Resource's Meta class, the new things to add are:
    view_name, the string for the view you want to call for your resource
    doc_class, the couchdbkit class you want to use as part of your serialization.

    For performance reasons, you should use the CoucdbkitTastyPaginator to leverage the skip/offset features of the
    existent couchdbkit/restkit api.

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

    def _get_limit_skip(self, request):
        """
        Tastypie api assumes offset as limit, but couchland it's skip
        """
        if request is not None:
            limit_option = request.GET.get('limit', self._meta.limit)
            skip_option = request.GET.get('offset', 0)
        else:
            limit_option = self._meta.limit
            skip_option = 0
        return limit_option, skip_option


    def get_object_list(self, request):
        """
        Assumes that the document type and the view correspond
        """
        #tune the limits for couch instead of grabbing everything

        limit_option, skip_option = self._get_limit_skip(request)
        results = self._meta.doc_class.view(self._meta.view_name, include_docs=True, skip=skip_option, limit=limit_option).all()
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


class ParameterizedResource(CouchdbkitResource):

    """
    More refined CouchDBkitResource, converts return values to datatables.net compatible json. Work in progress, as this class was created because DataTables mixin didn't seem to work.
    Also, datatables params can be tweaked so serialization alteration here needn't be necessary.
    """
    def get_object_list(self, request):
        """
        Assumes that the document type and the view correspond
        """
        limit_option, skip_option = self._get_limit_skip(request)
        results = self._meta.doc_class.view(self._meta.view_name, include_docs=True, limit=limit_option, skip=skip_option).all()
        return results

    def obj_get_list(self, request=None, **kwargs):
        limit_option, skip_option = self._get_limit_skip(request)
        results = self._meta.doc_class.view(self._meta.view_name, include_docs=True, key=request.user.username,  skip=skip_option, limit=limit_option).all()
        return results

    def obj_get(self, request=None, **kwargs):
        """
        Assume a fully formed couchdbkit document.
        """
        document = self._doctype().get(kwargs['pk'])
        return document
    def get_list(self, request, **kwargs):
        """
        Returns a serialized list of resources.

        Calls ``obj_get_list`` to provide the data, then handles that result
        set and serializes it.

        Should return a HttpResponse (200 OK).
        """
        # TODO: Uncached for now. Invalidation that works for everyone may be
        #       impossible.
        objects = self.obj_get_list(request=request, **self.remove_api_resource_names(kwargs))
        sorted_objects = self.apply_sorting(objects, options=request.GET)

        paginator = self._meta.paginator_class(request.GET, sorted_objects, resource_uri=self.get_resource_list_uri(), limit=self._meta.limit)
        to_be_serialized = paginator.page()
        to_be_serialized['aaData'] = to_be_serialized['objects']
        del(to_be_serialized['objects'])

        # Dehydrate the bundles in preparation for serialization.
        bundles = [self.build_bundle(obj=obj, request=request) for obj in to_be_serialized['aaData']]
        to_be_serialized['aaData'] = [self.full_dehydrate(bundle) for bundle in bundles]
        to_be_serialized = self.alter_list_data_to_serialize(request, to_be_serialized)
        return self.create_response(request, to_be_serialized)