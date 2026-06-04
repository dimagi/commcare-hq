import logging
import os
import tempfile
from abc import ABCMeta, abstractmethod
from collections import defaultdict
from contextlib import contextmanager

from django.apps import apps
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

logger = logging.getLogger(__name__)

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


class IdCache:
    """Per-dump cache of parent ids, keyed by ``(id_field, db_alias)``.

    Populated while a parent model (e.g. ``CommCareCase``) is dumped and read
    back when its child models are dumped, so the domain's parent ids are
    resolved from the database once instead of once per child model. Backed by
    one temp file per key; ids are sorted on ``finalize`` so the downstream
    ``__in`` queries hit a localized range of the child's id index.
    """

    def __init__(self, root_dir):
        self._root_dir = root_dir
        self._writers = {}

    @classmethod
    @contextmanager
    def open(cls):
        with tempfile.TemporaryDirectory(prefix='dump_id_cache_') as root_dir:
            cache = cls(root_dir)
            try:
                yield cache
            finally:
                cache._close_writers()

    def _path(self, id_field, db_alias):
        return os.path.join(self._root_dir, f'{id_field}.{db_alias}')

    def record(self, id_field, db_alias, value):
        key = (id_field, db_alias)
        writer = self._writers.get(key)
        if writer is None:
            path = self._path(id_field, db_alias)
            logger.info("Writing %s id list to %s", id_field, path)
            writer = self._writers[key] = open(path, 'w')
        writer.write(f'{value}\n')

    def finalize(self, id_field):
        """Flush and sort every shard file for ``id_field``; called once the
        parent model has been fully dumped."""
        for key in [k for k in self._writers if k[0] == id_field]:
            self._writers.pop(key).close()
            path = self._path(*key)
            # one shard's ids, sorted so downstream __in lists are contiguous;
            # an external sort would avoid this transient in-memory load
            with open(path) as f:
                ids = sorted(line.rstrip('\n') for line in f)
            with open(path, 'w') as f:
                f.writelines(f'{id_}\n' for id_ in ids)
            logger.info("Finalized %s id list (%s ids) at %s", id_field, len(ids), path)

    def read(self, id_field, db_alias):
        """Yield the cached ids for ``(id_field, db_alias)``, or ``None`` if the
        parent was not dumped (the caller then falls back to the database)."""
        if (id_field, db_alias) in self._writers:
            return None  # not finalized; treat as absent
        path = self._path(id_field, db_alias)
        if not os.path.exists(path):
            return None
        return self._stream(path)

    @staticmethod
    def _stream(path):
        with open(path) as f:
            for line in f:
                yield line.rstrip('\n')

    def _close_writers(self):
        for writer in self._writers.values():
            writer.close()
        self._writers.clear()


class _ParentIDFilter(DomainFilter):
    """Dump child rows by the ids of their parent rows in a domain.

    Subclasses set ``parent_model_label`` (the model carrying ``domain``) and
    ``id_field`` (the natural id shared by parent and child, e.g. ``case_id``).
    Resolving the domain's parent ids and filtering children with
    ``<id_field>__in`` avoids joining child to parent on every page: the child
    query uses its own ``id_field`` index and the keyset cursor can prune,
    neither of which a join on the parent's ``domain`` allows.

    Parent and child must be sharded by ``id_field`` so the ids resolved on a
    given ``db_alias`` cover exactly the children stored on that shard. When an
    ``IdCache`` populated by the parent dump is supplied, the ids are read from
    it instead of re-querying the parent (several child models share one
    parent).
    """
    parent_model_label = None
    id_field = None

    def __init__(self, chunksize=1000):
        self.chunksize = chunksize

    def get_filters(self, domain_name, db_alias=None, id_cache=None):
        ids = id_cache.read(self.id_field, db_alias) if id_cache is not None else None
        if ids is None:
            ids = self._iter_ids_from_db(domain_name, db_alias)
        # Read ids in large batches, but keep the downstream ``__in`` lists
        # small enough to keep the child query plan tight.
        for id_chunk in chunked(ids, self.chunksize, list):
            yield Q(**{f'{self.id_field}__in': id_chunk})

    def _iter_ids_from_db(self, domain_name, db_alias):
        parent_model = apps.get_model(self.parent_model_label)
        # only(id_field) so the parent query selects just the id (plus pk), not whole rows
        queryset = parent_model.objects.using(db_alias).filter(domain=domain_name).only(self.id_field)
        parents = queryset_to_iterator(
            queryset,
            parent_model,
            limit=DEFAULT_CHUNK_SIZE,
            ignore_ordering=True,
            pagination_key=(self.id_field,),
        )
        return (getattr(parent, self.id_field) for parent in parents)


class CaseIDFilter(_ParentIDFilter):
    """Dump rows whose ``case_id`` belongs to a case in the domain."""
    parent_model_label = 'form_processor.CommCareCase'
    id_field = 'case_id'


class FormIDFilter(_ParentIDFilter):
    """Dump rows whose ``form_id`` belongs to a form in the domain."""
    parent_model_label = 'form_processor.XFormInstance'
    id_field = 'form_id'


class UnfilteredModelIteratorBuilder(object):
    def __init__(self, model_label, use_all_objects=False):
        self.model_label = model_label
        self.domain = self.model_class = self.db_alias = None
        self.use_all_objects = use_all_objects
        # exists to make iterators() compatible with subclasses that set pagination_key
        self.pagination_key = ('pk',)

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

    def querysets(self, id_cache=None):
        yield self._base_queryset()

    def count(self):
        return sum(q.count() for q in self.querysets())

    def iterators(self, chunk_size=DEFAULT_CHUNK_SIZE, id_cache=None):
        for queryset in self.querysets(id_cache):
            yield queryset_to_iterator(
                queryset, self.model_class, limit=chunk_size,
                ignore_ordering=True, pagination_key=self.pagination_key,
            )

    def build(self, domain, model_class, db_alias):
        return self.__class__(self.model_label, self.use_all_objects).prepare(domain, model_class, db_alias)


class FilteredModelIteratorBuilder(UnfilteredModelIteratorBuilder):
    def __init__(self, model_label, filter, use_all_objects=False, pagination_key=('pk',)):
        super(FilteredModelIteratorBuilder, self).__init__(model_label, use_all_objects)
        self.filter = filter
        self.pagination_key = pagination_key

    def build(self, domain, model_class, db_alias):
        return self.__class__(
            self.model_label, self.filter, self.use_all_objects, self.pagination_key
        ).prepare(domain, model_class, db_alias)

    def count(self):
        count = self.filter.count(self.domain)
        if count is not None:
            return count
        return super(FilteredModelIteratorBuilder, self).count()

    def querysets(self, id_cache=None):
        queryset = self._base_queryset()
        if isinstance(self.filter, _ParentIDFilter):
            filters = self.filter.get_filters(self.domain, db_alias=self.db_alias, id_cache=id_cache)
        else:
            filters = self.filter.get_filters(self.domain, db_alias=self.db_alias)
        for filter_ in filters:
            yield queryset.filter(filter_)


class UniqueFilteredModelIteratorBuilder(FilteredModelIteratorBuilder):
    def iterators(self, chunk_size=DEFAULT_CHUNK_SIZE, id_cache=None):
        # chunk_size is unused, but needed to preserve the base class signature
        def _unique(iterator):
            seen = set()
            for model in iterator:
                if model.pk not in seen:
                    seen.add(model.pk)
                    yield model

        for queryset in self.querysets(id_cache):
            yield _unique(queryset)
