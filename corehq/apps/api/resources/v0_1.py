import logging
import pdb
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
import simplejson
from tastypie.paginator import Paginator
from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.decorators import login_or_digest
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser
from corehq.elastic import get_es
from couchforms.models import XFormInstance
from tastypie import fields
from tastypie.authentication import Authentication
from tastypie.authorization import ReadOnlyAuthorization, DjangoAuthorization
from tastypie.exceptions import BadRequest
from tastypie.resources import Resource
from tastypie.serializers import Serializer
from dimagi.utils.decorators import inline


class ElasticPaginator(Paginator):
    def get_slice(self, limit, offset):
        """
        Slices the result set to the specified ``limit`` & ``offset``.
        """
        if not self.objects.has_key('error'):
            return self.objects['hits']['hits']
        else:
            return []

    def get_count(self):
        """
        Returns a count of the total number of objects seen.
        """

        #        pdb.set_trace()
        if self.objects.has_key('hits'):
            return self.objects['hits']['total']
        return 0


    def page(self):
        """
        Generates all pertinent data about the requested page.

        Handles getting the correct ``limit`` & ``offset``, then slices off
        the correct set of results and returns all pertinent metadata.

        objects are a RawES return set.

        {
        'took': int,
        'timed_out': bool,
        '_shards': {},
        'hits': {
                'total': int,
                'max_score': int,
                'hits': [] #results!
            }
        }
        """
        limit = self.get_limit()
        offset = self.get_offset()
        count = self.get_count()
        objects = self.get_slice(limit, offset)
        meta = {
            'offset': offset,
            'limit': limit,
            'total_count': count,
            'took': self.objects['took']
        }

        if limit:
            meta['previous'] = self.get_previous(limit, offset)
            meta['next'] = self.get_next(limit, offset, count)

        #[XFormInstance.wrap(x['_source']) for x in es_results['hits']['hits']]

        def wrap_forms(obs):
            for x in obs:
                yield XFormInstance.wrap(x['_source'])

        return {
            'objects': wrap_forms(objects),
            'meta': meta,
        }


class CustomXMLSerializer(Serializer):
    def to_etree(self, data, options=None, name=None, depth=0):
        etree = super(CustomXMLSerializer, self).to_etree(data, options, name, depth)
        id = etree.find('id')
        if id is not None:
            etree.attrib['id'] = id.findtext('.')
            etree.remove(id)
        return etree


class LoginAndDomainAuthentication(Authentication):
    def is_authenticated(self, request, **kwargs):
        PASSED_AUTH = 'is_authenticated'

        @login_or_digest
        def dummy(request, domain, **kwargs):
            return PASSED_AUTH

        if not kwargs.has_key('domain'):
            kwargs['domain'] = request.domain

        response = dummy(request, **kwargs)

        if response == PASSED_AUTH:
            return True
        else:
            return response


    def get_identifier(self, request):
        return request.couch_user.username


class CustomResourceMeta(object):
    authorization = ReadOnlyAuthorization()
    authentication = LoginAndDomainAuthentication()
    serializer = CustomXMLSerializer()


class CommCareUserResource(Resource):
    type = "user"
    id = fields.CharField(attribute='get_id', readonly=True, unique=True)
    username = fields.CharField(attribute='username', unique=True)
    first_name = fields.CharField(attribute='first_name')
    last_name = fields.CharField(attribute='last_name')
    default_phone_number = fields.CharField(attribute='default_phone_number', null=True)
    email = fields.CharField(attribute='email')
    phone_numbers = fields.ListField(attribute='phone_numbers')
    groups = fields.ListField(attribute='get_group_ids')
    user_data = fields.DictField(attribute='user_data')

    def obj_get(self, request, **kwargs):
        domain = kwargs['domain']
        pk = kwargs['pk']
        try:
            user = CommCareUser.get_by_user_id(pk, domain)
        except KeyError:
            user = None
        return user

    def obj_get_list(self, request, **kwargs):
        domain = kwargs['domain']
        group_id = request.GET.get('group')
        if group_id:
            group = Group.get(group_id)
            if not group or group.domain != domain:
                raise BadRequest('Project %s has no group with id=%s' % (domain, group_id))
            return list(group.get_users(only_commcare=True))
        else:
            return list(CommCareUser.by_domain(domain))

    class Meta(CustomResourceMeta):
        resource_name = 'user'


class CommCareCaseResource(Resource):
    type = "case"
    id = fields.CharField(attribute='get_id', readonly=True, unique=True)
    user_id = fields.CharField(attribute='user_id')
    date_modified = fields.CharField(attribute='modified_on')
    closed = fields.BooleanField(attribute='closed')
    date_closed = fields.CharField(attribute='closed_on', null=True)

    xforms = fields.ListField(attribute='xform_ids')

    properties = fields.ListField()

    indices = fields.ListField(null=True)

    def dehydrate_properties(self, bundle):
        return bundle.obj.get_json()['properties']

    def dehydrate_indices(self, bundle):
        return bundle.obj.get_json()['indices']

    def obj_get(self, request, **kwargs):
        case = CommCareCase.get(kwargs['pk'])
        # stupid "security"
        if case.domain == kwargs['domain'] and case.doc_type == 'CommCareCase':
            return case
        else:
            raise ObjectDoesNotExist()

    def obj_get_list(self, request, **kwargs):
        domain = kwargs['domain']
        closed_only = {
                          'true': True,
                          'false': False,
                          'any': True
                      }[request.GET.get('closed', 'false')]
        case_type = request.GET.get('case_type')

        key = [domain]
        if case_type:
            key.append(case_type)
        cases = CommCareCase.view('hqcase/all_cases' if closed_only else 'hqcase/open_cases',
                                  startkey=key,
                                  endkey=key + [{}],
                                  include_docs=True,
                                  reduce=False,
        ).all()

        return list(cases)


    class Meta(CustomResourceMeta):
        resource_name = 'case'


class XFormInstanceResource(Resource):
    type = "form"
    id = fields.CharField(attribute='get_id', readonly=True, unique=True)

    form = fields.DictField(attribute='get_form')
    type = fields.CharField(attribute='type')
    version = fields.CharField(attribute='version')
    uiversion = fields.CharField(attribute='uiversion')
#    metadata = fields.DictField(attribute='metadata')
    received_on = fields.DateTimeField(attribute="received_on")
    md5 = fields.CharField(attribute='xml_md5')
    #    top_level_tags = fields.DictField(attribute='top_level_tags') # seems redundant

    #properties = fields.ListField()

    #def dehydrate_properties(self, bundle):
    #    return bundle.obj.get_json()['properties']


    #source: https://github.com/llonchj/django-tastypie-elasticsearch
    def get_sorting(self, request, key="order_by"):
        order_by = request.GET.get(key)
        if order_by:
            l = []

            items = [i.strip() for i in order_by.split(",")]
            for item in items:
                order = "asc"
                if item.startswith("-"):
                    item = item[1:]
                    order = "desc"
                l.append({item: order})
            return l
        return None

    def obj_get(self, request, **kwargs):
        domain = kwargs['domain']
        form_id = kwargs['pk']

        form = XFormInstance.get(form_id)
        # stupid "security"
        if form.domain == domain and form.doc_type == 'XFormInstance':
            return form
        else:
            raise ObjectDoesNotExist()

    def obj_get_list(self, request, **kwargs):
        domain = request.domain
        sort = self.get_sorting(request)
        if sort is None:
            sort = [{'received_on': 'desc'}]

        lucene_query = request.GET.get('qs', None)

        @list
        @inline
        def get_filters():
            yield {"term": {"domain": domain}}
            #            if lucene_query is not None:
#            yield dict(query_string=dict(query=lucene_query))
        #                yield {"query_string": {"query": lucene_query}}
            raw_filters = request.GET.get('q', '')
            filters = raw_filters.split(',')
            for f in filters:
                kv = f.split(':')
                if len(kv) != 2:
                    continue
                if kv[0].startswith('-'):
                    yield {'not': {'term': {kv[0]: kv[1]}}}
                else:
                    yield {'term': {kv[0]: kv[1]}}


        es_query = {
            "query": {
                "filtered": {
                    "query": {
                        "query_string": {"query": lucene_query},
                    },
                    "filter": {
                        "and": get_filters
                    }
                },
                #                           "term": {"domain": domain},
                #                "bool": {
                #                    "must": get_filters
                #                },
                },
                'sort': sort,
                'from': request.GET.get('offset', 0),
                'size': request.GET.get('limit', 500)

        }
        if lucene_query is not None:
            #es_query["filter"]["query"] = {"query_string": { "query" : lucene_query}}
            pass

        print simplejson.dumps(es_query, indent=4)
        es_results = get_es().get('xforms/_search', data=es_query)

        if es_results.has_key('error'):
            logging.exception("Error in xform elasticsearch query: %s" % es_results['error'])
            return {'Error': "No data"}


        #        #transform the return value to something compatible with the report listing
        #        ret = {
        #            'skip': request.GET.get('offset', 0),
        #            'limit': request.GET.get('limit', 10)
        #            'rows': [{'doc': x['_source']} for x in es_results['hits']['hits']],
        #            'total_rows': es_results['hits']['total']
        #        }
        #        return ret
        #        return ret['hits']['hits']
        #        print simplejson.dumps(es_results['hits']['hits'], indent=4)
        print es_results['hits']['total']

        #return [XFormInstance.wrap(x['_source']) for x in es_results['hits']['hits']]
        return es_results


    class Meta(CustomResourceMeta):
        resource_name = 'form'
        authorization = DjangoAuthorization()
        authentication = LoginAndDomainAuthentication()
        paginator_class = ElasticPaginator
