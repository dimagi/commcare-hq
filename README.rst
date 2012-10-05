This is a simple app to help you schedule long running tasks for retrieval later when they're done.
Two modes of operation:  1:  sit and refresh page till it's done with a download link, or 2: send a "done" email with a link to a page with the resulting download.

If you want to server large binaries over a cache, you must have django-redis installed, otherwise python-memcached is all you need

There are a few settings you can use to tweak the default cache storage:

SOIL_DEFAULT_CACHE = 'soil.FileDownload' # or 'soil.CachedDownload'
SOIL_DEFAULT_CACHE = 'default'           # or 'memcached', 'redis', etc. 