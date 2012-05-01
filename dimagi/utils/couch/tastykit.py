from datetime import datetime
from tastypie import fields
import simplejson
from tastypie.bundle import Bundle
from tastypie.paginator import Paginator
from tastypie.resources import Resource

class CouchdbkitTastyPaginator(Paginator):
    """
    Override of the default Paginator for TastyPie - using couchdbkit, we can limit/paginate using the
    view API, but the slicing assumes we have a queryset, so to be more efficient, we do that in the get_list

    Note, page() as it stands right now is handled by the resource itself.  page() in the tastypie sense assumes a lazily loaded queryset
    while for couchdbkit, the data returned from the DB is exactly the data being shown.
    """
    def get_slice(self, limit, offset):
        """
        Since we are assuming that couchdbkit already paginated it, we will return all our objects.
        """
        return self.objects

class CouchdbkitViewExecutor(object):
    """
    Helper class to pass into the meta of our Couchdbkit Resource to help run queries, be it map or reduce views,
    as well as providing ways to manage parameters and special key values.
    """

    def __init__(self):

        #is reduce
        #reduce level
        #startkey, endkey
        #key
        #include_docs
        #skip
        #limit
        #view_nme

        pass



    def run_query(self, request, db, view_name, skip, limit):
        # results = self._meta.doc_class.view(self._meta.view_name, include_docs=True, skip=skip_option, limit=limit_option).all()

        return None


    def get_total(self):
        pass

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

    In order for this to work with datatables, you must override the sAjaxDataProp from aaData to objects

    meta properties:
    doc_class/object_class

    couchdb (if none, it's doc_class.get_db())

    include_all_props = True (just use all properties and dynamic properties from document) vs. or just the explicit fields set in the resource declaration (default True)

    """
    _id = fields.CharField(attribute='get_id')
    _rev = fields.CharField(attribute="_rev")


    def _db(self):
        """
        Using the doc_class, get the underlying db.
        """

        if hasattr(self._meta, 'couchdb'):
            return self._meta.couchdb
        else:
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

    def call_view(self, request, **kwargs):
        """
        Returns the db.view() function, but with all the custom logic necessary to run.

        This calls the default view in its entirety, your implementation should call it with more precision.
        """
        limit_option, skip_option = self._get_limit_skip(request)
        view_call = self._meta.doc_class.view(self._meta.view_name, include_docs=True, skip=skip_option, limit=limit_option)
        return view_call


    def _get_limit_skip(self, request):
        """
        Tastypie api assumes offset as limit, but couchland it's skip.  This checks DataTables inbound data
        but also does regular params as well.
        """
        if request is not None:
            if request.GET.get('iDisplayLength', None) is not None:
                limit_option = request.GET['iDisplayLength']
            else:
                limit_option = request.GET.get('limit', self._meta.limit)

            if request.GET.get('iDisplayStart', None) is not None:
                skip_option = request.GET.get('iDisplayStart', 0)
            else:
                skip_option = request.GET.get('offset', 0)
        else:
            limit_option = self._meta.limit
            skip_option = 0
        return limit_option, skip_option

    def compute_totals(self, request, **kwargs):
        """
        For computing the "x out of y entries" section, the view needs to be called again

        This ought to be overriden too
        """
        if hasattr(self, '_totals'):
            return self._totals
        else:
            if request.GET.get('username', None) is not None:
                ret =  self._meta.doc_class.view(self._meta.view_name, key=request.GET['username']).count()
            else:
                ret =  self._meta.doc_class.view(self._meta.view_name).count()
            self._totals = ret
            return ret

    def obj_get_list(self, request=None, **kwargs):
        """
        Assumes that the document type and the view correspond
        """
        #tune the limits for couch instead of grabbing everything

        results = self.call_view(request, **kwargs).all()
        return list(results)


    def full_dehydrate(self, bundle):
        """
        Override of full_dehydrate so as to allow for getting ALL properties from the document, and/or tastykit derived ones.
        """

        bundle = super(CouchdbkitResource, self).full_dehydrate(bundle)
        for prop_key in bundle.obj.properties().keys():
            bundle.data[prop_key] = bundle.obj[prop_key]

        for dyn_key, dyn_val in bundle.obj.dynamic_properties().items():
            bundle.data[dyn_key] = dyn_val
        bundle = self.dehydrate(bundle)
        return bundle

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
        to_be_serialized['objects'] = [self.full_dehydrate(bundle) for bundle in bundles]
        #total = len(to_be_serialized['objects'])
        to_be_serialized = self.alter_list_data_to_serialize(request, to_be_serialized)
        #display = len(to_be_serialized['objects'])

        #These are properties traditionally set by the paginator.page() call
        to_be_serialized['iTotalRecords'] = self.compute_totals(request, **kwargs)
        to_be_serialized['iTotalDisplayRecords'] = self.compute_totals(request, **kwargs)
        to_be_serialized['sEcho'] = request.GET.get('sEcho',1)

        return self.create_response(request, to_be_serialized)

    def obj_get(self, request=None, **kwargs):
        """
        Assume a fully formed couchdbkit document.
        """
        document = self._doctype().get(kwargs['pk'])
        return document


    #not implemented yet are the create/update/delete
    def obj_create(self, bundle, request=None, **kwargs):
        try:
            j = simplejson.loads(request.raw_post_data)
        except:
            pass
        bundle.obj = self._meta.doc_class.wrap(j)
        bundle.obj.save()
        #bundle = self.full_hydrate(bundle)
        #bundle.pk = bundle.obj._id
        #bundle.obj.pk = bundle.obj._id
        return bundle

    def obj_update(self, bundle, request=None, **kwargs):
        """
        Initial version works ok, though more verification is needed here
        """
        j = simplejson.loads(request.raw_post_data)
        res  = self._meta.doc_class.get_db().save_doc(j)
        bundle.obj = self._meta.doc_class.get(j['_id'])
        return bundle

    def obj_delete_list(self, request=None, **kwargs):
        pass

    def obj_delete(self, request=None, **kwargs):
        pass

    def rollback(self, bundles):
        pass

