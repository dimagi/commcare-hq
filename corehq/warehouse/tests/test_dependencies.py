from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase

from corehq.warehouse.models import get_cls_by_slug
from corehq.warehouse.const import ALL_TABLES


class TestDependencyCycle(SimpleTestCase):

    def test_dependency_cycle(self):

        for table_slug in ALL_TABLES:
            self.assertFalse(
                _has_cycles(table_slug, get_cls_by_slug(table_slug).dependencies()),
                '{} has a dependency cycle'.format(table_slug)
            )


def _has_cycles(table_slug, deps):
    if table_slug in deps:
        return True

    for dep_slug in deps:
        warehouse_cls = get_cls_by_slug(dep_slug)
        if _has_cycles(table_slug, warehouse_cls.dependencies()):
            return True

    return False
