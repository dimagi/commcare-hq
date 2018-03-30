from __future__ import absolute_import
from django.conf import settings
from django.contrib.postgres.fields.array import ArrayField
from django.db.models import CharField, IntegerField
from django.db.models.aggregates import Max
from django.db.models.expressions import Exists, F, Func, OuterRef, Value
from django.db.models.query import Q, QuerySet, EmptyResultSet
from django_cte import With
from mptt.models import MPTTModel, TreeManager

from .queryutil import ComparedQuerySet, TimingContext

int_field = IntegerField()
str_array = ArrayField(CharField())


class StrArray(Func):
    function = "Array"
    # HACK fool postgres with concat
    # https://stackoverflow.com/a/12488455/10840 (see comment by KajMagnus)
    template = "%(function)s[%(expressions)s || '']::varchar[]"
    output_field = str_array


class array_append(Func):
    function = "array_append"
    output_field = str_array


class array_length(Func):
    function = "array_length"
    template = "%(function)s(%(expressions)s, 1)"
    output_field = int_field


class AdjListManager(TreeManager):

    def cte_get_ancestors(self, node, ascending=False, include_self=False):
        """Query node ancestors

        :param node: A model instance or a QuerySet or Q object querying
        the adjacency list model. If a QuerySet, it should query a
        single value with something like `.values('id')`. If Q the
        `include_self` argument will be ignored.
        :param ascending: Order of results. The default (`False`) gets
        results in descending order (root ancestor first, immediate
        parent last).
        :param include_self:
        :returns: A `QuerySet` instance.
        """
        parent_col = self.model.parent_id_attr

        if isinstance(node, Q):
            where = node
        elif include_self:
            if isinstance(node, QuerySet):
                if _is_empty(node):
                    return self.none()
                where = Q(id__in=node.order_by())
            else:
                where = Q(id=node.id)
        elif isinstance(node, QuerySet):
            if _is_empty(node):
                return self.none()
            where = Q(id__in=node.order_by().values(parent_col))
        else:
            where = Q(id=getattr(node, parent_col))

        def make_cte_query(cte):
            return self.filter(where).order_by().values(
                "id",
                parent_col,
                _depth=Value(0, output_field=int_field),
            ).union(
                cte.join(
                    self.all().order_by(),
                    id=getattr(cte.col, parent_col)
                ).values(
                    "id",
                    parent_col,
                    _depth=cte.col._depth + Value(1, output_field=int_field),
                ),
            )

        cte = With.recursive(make_cte_query)
        return (
            cte
            .join(self.all(), id=cte.col.id)
            .with_cte(cte)
            .order_by(("" if ascending else "-") + "{}._depth".format(cte.name))
        )

    def cte_get_descendants(self, node, include_self=False):
        """Query node descendants

        :param node: A model instance or a QuerySet or Q object querying
        the adjacency list model. If a QuerySet, it should query a
        single value with something like `.values('id')`. If Q the
        `include_self` argument will be ignored.
        :returns: A `QuerySet` instance.
        """
        parent_col = self.model.parent_id_attr
        ordering_col = self.model.ordering_col_attr

        discard_dups = False
        if isinstance(node, Q):
            where = node
            discard_dups = True
        elif include_self:
            if isinstance(node, QuerySet):
                if _is_empty(node):
                    return self.none()
                where = Q(id__in=node.order_by())
                discard_dups = True
            else:
                where = Q(id=node.id)
        elif isinstance(node, QuerySet):
            if _is_empty(node):
                return self.none()
            where = Q(**{parent_col + "__in": node.order_by()})
            discard_dups = True
        else:
            where = Q(**{parent_col: node.id})

        def make_cte_query(cte):
            return self.filter(where).order_by().values(
                "id",
                _cte_ordering=StrArray(ordering_col),
            ).union(
                cte.join(
                    self.all().order_by(),
                    **{parent_col: cte.col.id}
                ).annotate(
                    _cte_ordering=array_append(
                        cte.col._cte_ordering,
                        F(ordering_col),
                    )
                ).values(
                    "id",
                    "_cte_ordering",
                ),
                all=True,
            )
        cte = With.recursive(make_cte_query)
        ctes = [cte]

        if discard_dups:
            # Remove duplicates when the supplied Queryset or Q object
            # may contain/match both parents and children. For a given
            # id, retain the row with the longest path. TODO remove this
            # and ensure duplicates do not matter or the criteria never
            # matches both parents and children in all calling code.
            xdups = With(
                cte.queryset().annotate(
                    max_len=array_length(
                        F("_cte_ordering"),
                        output_field=int_field
                    ),
                ).distinct("id").order_by(
                    "id",
                    "-max_len",
                ).values(
                    "id",
                    "_cte_ordering",
                ),
                name="xdups"
            )
            ctes.append(xdups)
            cte = xdups

        query = (
            cte
            .join(self.all(), id=cte.col.id)
            # EXISTS helps postgres avoid seq scan on locations table
            # EXPLAIN ANALYZE showed postgres estimated > 1 million rows in the
            # recursive CTE on softlayer when there were actually only 6 rows.
            # The seq scan on the locations table took ~1 minute; EXISTS -> 3ms.
            .annotate(_cte_exists=Exists(cte.queryset().filter(id=OuterRef("id"))))
            .filter(_cte_exists=True)
            # TODO uncomment when removing MPTT
            #.order_by(cte.col._cte_ordering)
        )
        for item in ctes:
            query = query.with_cte(item)
        return query

    def cte_get_queryset_ancestors(self, node, include_self=False):
        return (
            self.cte_get_ancestors(node, include_self=include_self)
            # TODO remove this order_by when removing MPTT
            .order_by(self.tree_id_attr, self.left_attr)
        )

    cte_get_queryset_descendants = cte_get_descendants

    def mptt_get_queryset_ancestors(self, node, *args, **kw):
        if isinstance(node, Q):
            node = self.filter(node)
        return super(AdjListManager, self).get_queryset_ancestors(node, *args, **kw)

    def mptt_get_queryset_descendants(self, node, *args, **kw):
        if isinstance(node, Q):
            node = self.filter(node)
        return super(AdjListManager, self).get_queryset_descendants(node, *args, **kw)

    def get_queryset_ancestors(self, queryset, include_self=False):
        timing = TimingContext("get_queryset_ancestors")
        mptt_qs = cte_qs = queryset
        if isinstance(queryset, ComparedQuerySet):
            mptt_qs = queryset._mptt_set
            cte_qs = queryset._cte_set
        with timing("mptt"):
            mptt_set = self.mptt_get_queryset_ancestors(mptt_qs, include_self)
        if settings.IS_LOCATION_CTE_ENABLED:
            with timing("cte"):
                cte_set = self.cte_get_queryset_ancestors(cte_qs, include_self)
        else:
            cte_set = None
        return ComparedQuerySet(mptt_set, cte_set, timing)

    def get_queryset_descendants(self, queryset, include_self=False):
        timing = TimingContext("get_queryset_descendants")
        mptt_qs = cte_qs = queryset
        if isinstance(queryset, ComparedQuerySet):
            mptt_qs = queryset._mptt_set
            cte_qs = queryset._cte_set
        with timing("mptt"):
            mptt_set = self.mptt_get_queryset_descendants(mptt_qs, include_self)
        if settings.IS_LOCATION_CTE_ENABLED:
            with timing("cte"):
                cte_set = self.cte_get_queryset_descendants(cte_qs, include_self)
        else:
            cte_set = None
        return ComparedQuerySet(mptt_set, cte_set, timing)


class AdjListModel(MPTTModel):
    """Base class for tree models implemented with adjacency list pattern

    For more on adjacency lists, see
    https://explainextended.com/2009/09/24/adjacency-list-vs-nested-sets-postgresql/
    """

    parent_id_attr = 'parent_id'
    ordering_col_attr = 'name'

    objects = AdjListManager()

    class Meta:
        abstract = True

    def mptt_get_ancestors(self, **kw):
        # VERIFIED does not call self.objects.get_queryset_ancestors
        return super(AdjListModel, self).get_ancestors(**kw)

    def mptt_get_descendants(self, **kw):
        # VERIFIED does not call self.objects.get_queryset_descendants
        return super(AdjListModel, self).get_descendants(**kw)

    def get_ancestors(self, **kw):
        """
        Returns a Queryset of all ancestor locations of this location
        """
        timing = TimingContext("get_ancestors")
        with timing("mptt"):
            mptt_set = self.mptt_get_ancestors(**kw)
        if settings.IS_LOCATION_CTE_ENABLED:
            with timing("cte"):
                cte_set = type(self).objects.cte_get_ancestors(self, **kw)
        else:
            cte_set = None
        return ComparedQuerySet(mptt_set, cte_set, timing)

    def get_descendants(self, **kw):
        """
        Returns a Queryset of all descendant locations of this location
        """
        timing = TimingContext("get_descendants")
        with timing("mptt"):
            mptt_set = self.mptt_get_descendants(**kw)
        if settings.IS_LOCATION_CTE_ENABLED:
            with timing("cte"):
                cte_set = type(self).objects.cte_get_descendants(self, **kw)
        else:
            cte_set = None
        return ComparedQuerySet(mptt_set, cte_set, timing)


def _is_empty(queryset):
    query = queryset.query
    if query.is_empty():
        return True
    try:
        query.sql_with_params()
    except EmptyResultSet:
        return True
    return False
