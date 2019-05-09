from __future__ import absolute_import, unicode_literals

from tastypie.paginator import Paginator


class NoCountingPaginator(Paginator):
    """
    The default paginator contains the total_count value, which shows how
    many objects are in the underlying object list. Obtaining this data from
    the database is inefficient, especially with large datasets, and unfiltered API requests.

    This class does not perform any counting and return 'null' as the value of total_count.

    See:
        * http://django-tastypie.readthedocs.org/en/latest/paginator.html
        * http://wiki.postgresql.org/wiki/Slow_Counting
    """

    def get_previous(self, limit, offset):
        if offset - limit < 0:
            return None

        return self._generate_uri(limit, offset-limit)

    def get_next(self, limit, offset, count):
        """
        Always generate the next URL even if there may be no records.
        """
        return self._generate_uri(limit, offset+limit)

    def get_count(self):
        """
        Don't do any counting.
        """
        return None


class DoesNothingPaginator(Paginator):
    def page(self):
        return {
            self.collection_name: self.objects,
            "meta": {'total_count': self.get_count()}
        }
