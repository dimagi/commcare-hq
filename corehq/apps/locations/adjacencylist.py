from __future__ import absolute_import
from django.db.models import IntegerField
from django.db.models.expressions import Value
from django.db.models.query import Q, QuerySet
from django_cte import With
from mptt.models import MPTTModel, TreeManager

from .queryutil import ComparedQuerySet, TimingContext

int_field = IntegerField()


class AdjListManager(TreeManager):

    def cte_get_ancestors(self, node, ascending=False, include_self=False):
        """Query node ancestors

        :param node: A model instance or a QuerySet or Q object querying
        the adjacency list model. If a QuerySet, it should query a
        single value with something like `.values('pk')`. If Q the
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
                where = Q(pk__in=node)
            else:
                where = Q(pk=node.id)
        elif isinstance(node, QuerySet):
            where = Q(pk__in=node.values(parent_col))
        else:
            where = Q(pk=getattr(node, parent_col))

        def make_cte_query(cte):
            return self.filter(where).values(
                "pk",
                parent_col,
                _depth=Value(0, output_field=int_field),
            ).union(
                cte.join(self.model, pk=getattr(cte.col, parent_col)).values(
                    "pk",
                    parent_col,
                    _depth=cte.col._depth + Value(1, output_field=int_field),
                ),
            )

        cte = With.recursive(make_cte_query)
        return (
            cte
            .join(self.all(), pk=cte.col.pk)
            .with_cte(cte)
            .order_by(("" if ascending else "-") + "{}._depth".format(cte.name))
        )

    def cte_get_descendants(self, node, include_self=False):
        """Query node descendants

        :param node: A model instance or a QuerySet or Q object querying
        the adjacency list model. If a QuerySet, it should query a
        single value with something like `.values('pk')`. If Q the
        `include_self` argument will be ignored.
        :returns: A `QuerySet` instance.
        """
        parent_col = self.model.parent_id_attr

        if isinstance(node, Q):
            where = node
        elif include_self:
            if isinstance(node, QuerySet):
                where = Q(pk__in=node)
            else:
                where = Q(pk=node.id)
        elif isinstance(node, QuerySet):
            where = Q(**{parent_col + "__in": node})
        else:
            where = Q(**{parent_col: node.id})

        def make_cte_query(cte):
            return self.filter(where).values(
                "pk",
                parent_col,
            ).union(
                cte.join(self.model, **{parent_col: cte.col.pk}).values(
                    "pk",
                    parent_col,
                ),
            )

        cte = With.recursive(make_cte_query)
        return cte.join(self.all(), pk=cte.col.pk).with_cte(cte)

    cte_get_queryset_ancestors = cte_get_ancestors
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
        with timing("cte"):
            cte_set = self.cte_get_queryset_ancestors(cte_qs, include_self)
        return ComparedQuerySet(mptt_set, cte_set, timing)

    def get_queryset_descendants(self, queryset, include_self=False):
        timing = TimingContext("get_queryset_descendants")
        mptt_qs = cte_qs = queryset
        if isinstance(queryset, ComparedQuerySet):
            mptt_qs = queryset._mptt_set
            cte_qs = queryset._cte_set
        with timing("mptt"):
            mptt_set = self.mptt_get_queryset_descendants(mptt_qs, include_self)
        with timing("cte"):
            cte_set = self.cte_get_queryset_descendants(cte_qs, include_self)
        return ComparedQuerySet(mptt_set, cte_set, timing)


class AdjListModel(MPTTModel):
    """Base class for tree models implemented with adjacency list pattern

    For more on adjacency lists, see
    https://explainextended.com/2009/09/24/adjacency-list-vs-nested-sets-postgresql/
    """

    parent_id_attr = 'parent_id'

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
        timing = TimingContext("get_ancestors")
        with timing("mptt"):
            mptt_set = self.mptt_get_ancestors(**kw)
        with timing("cte"):
            cte_set = type(self).objects.cte_get_ancestors(self, **kw)
        return ComparedQuerySet(mptt_set, cte_set, timing)

    def get_descendants(self, **kw):
        timing = TimingContext("get_descendants")
        with timing("mptt"):
            mptt_set = self.mptt_get_descendants(**kw)
        with timing("cte"):
            cte_set = type(self).objects.cte_get_descendants(self, **kw)
        return ComparedQuerySet(mptt_set, cte_set, timing)
