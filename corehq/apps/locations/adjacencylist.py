from django.core.exceptions import EmptyResultSet
from django.db import models
from django.db.models.expressions import Exists, F, Func, OuterRef, Value
from django.db.models.query import Q, QuerySet

from django_cte import With


class str_array(Func):
    function = "Array"
    # HACK fool postgres with concat
    # https://stackoverflow.com/a/12488455/10840 (see comment by KajMagnus)
    template = "%(function)s[%(expressions)s || '']::varchar[]"
    output_field = models.Field()


class array_append(Func):
    function = "array_append"
    output_field = models.Field()


class array_length(Func):
    function = "array_length"
    template = "%(function)s(%(expressions)s, 1)"
    output_field = models.Field()


class AdjListManager(models.Manager):

    def get_ancestors(self, node, ascending=False, include_self=False):
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
            where = Q(id__in=node.order_by().values("parent_id"))
        else:
            where = Q(id=node.parent_id)

        def make_cte_query(cte):
            return self.filter(where).order_by().annotate(
                _depth=Value(0, output_field=models.IntegerField()),
            ).union(
                cte.join(
                    self.all().order_by(),
                    id=cte.col.parent_id,
                ).annotate(
                    _depth=cte.col._depth + Value(1, output_field=models.IntegerField()),
                ),
            )

        cte = With.recursive(make_cte_query)
        return (
            cte.queryset()
            .with_cte(cte)
            .order_by(("" if ascending else "-") + "_depth")
        )

    def get_descendants(self, node, include_self=False):
        """Query node descendants

        :param node: A model instance or a QuerySet or Q object querying
        the adjacency list model. If a QuerySet, it should query a
        single value with something like `.values('id')`. If Q the
        `include_self` argument will be ignored.
        :returns: A `QuerySet` instance.
        """
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
            where = Q(parent_id__in=node.order_by())
            discard_dups = True
        else:
            where = Q(parent_id=node.id)

        def make_cte_query(cte):
            return self.filter(where).order_by().annotate(
                _cte_ordering=str_array(ordering_col),
            ).union(
                cte.join(
                    self.all().order_by(),
                    parent_id=cte.col.id,
                ).annotate(
                    _cte_ordering=array_append(
                        cte.col._cte_ordering,
                        F(ordering_col),
                    )
                ),
                all=True,
            )
        cte = With.recursive(make_cte_query)
        query = cte.queryset().with_cte(cte)

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
                        output_field=models.Field()
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
            query = query.annotate(
                _exclude_dups=Exists(SubQueryset(xdups.queryset().filter(
                    id=OuterRef("id"),
                    _cte_ordering=OuterRef("_cte_ordering"),
                )))
            ).filter(_exclude_dups=True).with_cte(xdups)

        return query.order_by(cte.col._cte_ordering)

    def get_queryset_ancestors(self, queryset, include_self=False):
        return self.get_ancestors(queryset, include_self=include_self)

    def get_queryset_descendants(self, queryset, include_self=False):
        return self.get_descendants(queryset, include_self=include_self)

    def root_nodes(self):
        return self.all().filter(parent_id__isnull=True)


class AdjListModel(models.Model):
    """Base class for tree models implemented with adjacency list pattern

    For more on adjacency lists, see
    https://explainextended.com/2009/09/24/adjacency-list-vs-nested-sets-postgresql/
    """

    ordering_col_attr = 'name'

    objects = AdjListManager()

    class Meta:
        abstract = True

    def get_ancestors(self, **kw):
        """
        Returns a Queryset of all ancestor locations of this location
        """
        return type(self).objects.get_ancestors(self, **kw)

    def get_descendants(self, **kw):
        """
        Returns a Queryset of all descendant locations of this location
        """
        return type(self).objects.get_descendants(self, **kw)

    def get_children(self):
        return self.children.all()


def _is_empty(queryset):
    query = queryset.query
    if query.is_empty():
        return True
    try:
        query.sql_with_params()
    except EmptyResultSet:
        return True
    return False


class SubQueryset(object):
    """A QuerySet-like object that can be pickled

    Use with `django.db.models.expressions.Subquery` or
    `django.db.models.expressions.Exists` in combination with a
    `QuerySet` that references an outer CTE name, which cannot be
    pickled because the query is evaluated at pickle time.
    """

    # At the time of writing, Subquery and Exists only referenced two
    # attributes of QuerySet other than `query`: `all` and `order_by`

    def __init__(self, queryset):
        self.query = queryset.query.clone()

    def all(self):
        return SubQueryset(self)

    def order_by(self, *field_names):
        assert self.query.can_filter(), \
            "Cannot reorder a query once a slice has been taken."
        obj = SubQueryset(self)
        obj.query.clear_ordering(force_empty=False)
        obj.query.add_ordering(*field_names)
        return obj
