from abc import ABCMeta, abstractmethod
from collections import defaultdict

from django.db.models import Q

from dimagi.utils.chunked import chunked
from dimagi.utils.couch.database import iter_docs

from corehq.apps.dump_reload.couch.dump import DOC_PROVIDERS_BY_DOC_TYPE
from corehq.blobs.models import BlobMeta
from corehq.sql_db.util import (
    get_db_alias_for_partitioned_doc,
    get_db_aliases_for_partitioned_query,
)
from corehq.util.queries import queryset_to_iterator

DEFAULT_CHUNK_SIZE = 5000


class DomainFilter(metaclass=ABCMeta):
    @abstractmethod
    def get_filters(self, domain_name, db_alias=None):
        """Return a list of filters. Each filter will be applied to a queryset independently
        of the others."""
        raise NotImplementedError()

    def count(self, domain_name):
        return None


class SimpleFilter(DomainFilter):
    def __init__(self, filter_kwarg):
        self.filter_kwarg = filter_kwarg

    def get_filters(self, domain_name, db_alias=None):
        return [Q(**{self.filter_kwarg: domain_name})]


class ManyFilters(DomainFilter):
    """
    Filter by multiple filter kwargs. Filters are ANDed
    """
    def __init__(self, *filter_kwargs):
        assert filter_kwargs, 'Please set one of more filter_kwargs'
        self.filter_kwargs = filter_kwargs

    def get_filters(self, domain_name, db_alias=None):
        filter_ = Q(**{self.filter_kwargs[0]: domain_name})
        for filter_kwarg in self.filter_kwargs[1:]:
            filter_ &= Q(**{filter_kwarg: domain_name})
        return [filter_]


class UsernameFilter(DomainFilter):
    def __init__(self, usernames=None):
        self.usernames = usernames

    def count(self, domain_name):
        return len(self.usernames) if self.usernames is not None else None

    def get_filters(self, domain_name, db_alias=None):
        """
        :return: A generator of filters each filtering for at most 500 users.
        """
        from corehq.apps.users.dbaccessors import get_all_usernames_by_domain
        if self.usernames:
            usernames = self.usernames
        else:
            usernames = get_all_usernames_by_domain(domain_name)
        for chunk in chunked(usernames, 500):
            filter = Q()
            for username in chunk:
                filter |= Q(username__iexact=username)
            yield filter


class IDFilter(DomainFilter):
    def __init__(self, field, ids, chunksize=1000):
        self.field = field
        self.ids = ids
        self.chunksize = chunksize

    def count(self, domain_name):
        return len(self.get_ids(domain_name))

    def get_ids(self, domain_name, db_alias=None):
        return self.ids

    def get_filters(self, domain_name, db_alias=None):
        for chunk in chunked(self.get_ids(domain_name, db_alias=db_alias), self.chunksize):
            query_kwarg = f'{self.field}__in'
            yield Q(**{query_kwarg: chunk})


class CaseIDFilter(IDFilter):
    """Filter a case-owned model to a domain by its case_ids.

    Streams the domain's case_ids for a shard and yields them in
    ``Q(case_id__in=chunk)`` batches. This avoids joining the model back to
    ``CommCareCase`` (via ``case__domain``) just to resolve the domain, seeking the
    model's own indexed ``case_id`` column instead.

    Case IDs are not chunked in sorted order, so the final results will not
    be globally sorted. Results for each case id chunk will be sorted as
    necessary for pagination, but will not be sorted with respect to the results
    for other chunks.

    Limitation: Consumers must paginate by ``('case_id', 'pk')``, not a deeper key like
    ``('case_id', 'server_date', 'pk')``. A deeper key performs atrociously for unintuitive
    reasons. It surfaces on queries where the cursor
    case_id is greater than the alphabetically first case_id in the chunk, and results in
    (I think) a linear index scan of a huge range from the first case_id to the cursor case_id
    that returns no results (because they're all less than the cursor). This pathological
    behavior may be fixed in PG 17+.
    """

    def __init__(self, chunksize=1000):
        super().__init__('case_id', None, chunksize=chunksize)

    def get_ids(self, domain_name, db_alias=None):
        """Stream the domain's case_ids on a shard, paginating by ``(type, id)``"""
        from corehq.form_processor.models import CommCareCase
        queryset = (
            CommCareCase.objects.using(db_alias)
            .filter(domain=domain_name)
            .only('case_id', 'type')
        )
        for case in queryset_to_iterator(
            queryset, CommCareCase, limit=DEFAULT_CHUNK_SIZE,
            ignore_ordering=True, pagination_key=('type', 'id'),
        ):
            yield case.case_id

    def count(self, domain_name):
        # count is per-shard but db_alias is unknown here, and IDFilter.count would
        # call get_ids() against the wrong (non-partition) database. Return None so
        # the builder counts each Q(case_id__in=...) queryset per shard instead.
        return None


class UserIDFilter(IDFilter):
    def __init__(self, user_id_field, include_web_users=True):
        super().__init__(user_id_field, None)
        self.include_web_users = include_web_users

    def get_ids(self, domain_name, db_alias=None):
        from corehq.apps.users.dbaccessors import get_all_user_ids_by_domain
        return get_all_user_ids_by_domain(domain_name, include_web_users=self.include_web_users)


class MultimediaBlobMetaFilter(IDFilter):
    """
    BlobMeta for multimedia references the "<shared>" domain which is not the domain being dumped.
    """
    def __init__(self):
        # 'id' is used in query (e.g., ...filter(id__in=blobmeta_ids))
        super().__init__('id', None)
        self.ids_by_db = None

    def count(self, domain_name):
        count = 0
        for db in get_db_aliases_for_partitioned_query():
            count += len(self.get_ids(domain_name, db_alias=db))
        return count

    def get_ids(self, domain_name, db_alias=None):
        """
        Rather than redo work for each db shard, the first time this is called it collects the blobmeta ids
        for every db shard, and is ready to return the list on the next call. This does mean the map is held
        in memory, but it only stores BlobMeta primary keys, and it doesn't seem likely that a domain will
        have an unmanageable number of multimedia blobs.
        """
        if self.ids_by_db:
            return self.ids_by_db[db_alias]

        self.ids_by_db = defaultdict(list)
        multimedia_provider = DOC_PROVIDERS_BY_DOC_TYPE['CommCareMultimedia']
        for doc_class, doc_ids in multimedia_provider.get_doc_ids(domain_name):
            couch_db = doc_class.get_db()
            for doc in iter_docs(couch_db, doc_ids):
                # BlobMeta is partitioned by parent_id, which is the CommCareMultimedia id
                db_for_meta = get_db_alias_for_partitioned_doc(doc['_id'])
                # wrapping ensures consistent interface for obtaining key attr from blob metas
                obj = doc_class.get_doc_class(doc['doc_type']).wrap(doc)
                for name, blob_meta in obj.blobs.items():
                    meta = BlobMeta.objects.partitioned_query(doc["_id"]).get(
                        parent_id=doc["_id"], key=blob_meta["key"]
                    )
                    self.ids_by_db[db_for_meta].append(meta.pk)
        return self.ids_by_db[db_alias]


class UnfilteredModelIteratorBuilder(object):
    def __init__(self, model_label, use_all_objects=False):
        self.model_label = model_label
        self.domain = self.model_class = self.db_alias = None
        self.use_all_objects = use_all_objects
        # defaults so iterators() works for subclasses that set these
        self.pagination_key = ('pk',)
        self.use_fk_index_hint = False

    def prepare(self, domain, model_class, db_alias):
        self.domain = domain
        self.model_class = model_class
        self.db_alias = db_alias
        return self

    def _base_queryset(self):
        assert self.domain and self.model_class and self.db_alias, "Unprepared IteratorBuilder"
        objects = (
            self.model_class.all_objects if self.use_all_objects else self.model_class._default_manager
        )
        return objects.using(self.db_alias)

    def querysets(self):
        yield self._base_queryset()

    def count(self):
        return sum(q.count() for q in self.querysets())

    def iterators(self, chunk_size=DEFAULT_CHUNK_SIZE):
        for queryset in self.querysets():
            yield queryset_to_iterator(
                queryset, self.model_class, limit=chunk_size,
                ignore_ordering=True, pagination_key=self.pagination_key,
                use_fk_index_hint=self.use_fk_index_hint,
            )

    def build(self, domain, model_class, db_alias):
        return self.__class__(self.model_label, self.use_all_objects).prepare(domain, model_class, db_alias)


class FilteredModelIteratorBuilder(UnfilteredModelIteratorBuilder):
    def __init__(self, model_label, filter, use_all_objects=False, pagination_key=('pk',),
                 use_fk_index_hint=False):
        super(FilteredModelIteratorBuilder, self).__init__(model_label, use_all_objects)
        self.filter = filter
        self.pagination_key = pagination_key
        self.use_fk_index_hint = use_fk_index_hint

    def build(self, domain, model_class, db_alias):
        return self.__class__(
            self.model_label, self.filter, self.use_all_objects, self.pagination_key,
            self.use_fk_index_hint,
        ).prepare(domain, model_class, db_alias)

    def count(self):
        count = self.filter.count(self.domain)
        if count is not None:
            return count
        return super(FilteredModelIteratorBuilder, self).count()

    def querysets(self):
        queryset = self._base_queryset()
        filters = self.filter.get_filters(self.domain, db_alias=self.db_alias)
        for filter_ in filters:
            yield queryset.filter(filter_)


class UniqueFilteredModelIteratorBuilder(FilteredModelIteratorBuilder):
    def iterators(self, chunk_size=DEFAULT_CHUNK_SIZE):
        # chunk_size is unused, but needed to preserve the base class signature
        def _unique(iterator):
            seen = set()
            for model in iterator:
                if model.pk not in seen:
                    seen.add(model.pk)
                    yield model

        for queryset in self.querysets():
            yield _unique(queryset)
