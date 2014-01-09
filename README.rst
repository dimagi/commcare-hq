Django Soil
===========

This is a simple app to help you schedule long running tasks for retrieval later when they're done.
It has two modes of operation:

    #. Sit and refresh page till it's done with a download link.
    #. Send a "done" email with a link to a page with the resulting download.

If you want to server large binaries over a cache, you must have django-redis installed, otherwise python-memcached is all you need

There are a few settings you can use to tweak the default cache storage::

    SOIL_DEFAULT_CACHE = 'soil.FileDownload' # or 'soil.CachedDownload'
    SOIL_DEFAULT_CACHE = 'default'           # or 'memcached', 'redis', etc. 
