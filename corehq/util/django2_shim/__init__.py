"""
A package allowing cleanup of import changes after migrating to Django 2.

This package is structured such that

    form corehq.util.django2_shim.x.x import y

will work in both Django 1 and Django 2, and that once we are on django 2
we can replace `from corehq.util.django2_shim.` with `from django.` throughout
and remove this package.

"""
