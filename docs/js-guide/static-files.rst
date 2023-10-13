Static Files
============

Static files include any ``css``, ``js``, and image files that are not
dynamically generated during runtime. ``css`` is typically compiled from
``less`` and minified prior to server runtime. ``js`` files are
collected, combined, and minified prior to server runtime. As of this
writing we don’t compile our JavaScript from a higher level scripting
language. Image files generally stay as-is. The only ‘dynamic’ images
come from file attachments in our database.

Due to their static natures, the primary objective for static files is
to make as few requests to them during page load, meaning that our goal
is to combine static files into one larger, minified file when possible.
An additional goal is to ensure that the browser caches the static files
it is served to make subsequent page loads faster.

Collectstatic
-------------

Collectstatic is a Django management command that combs through each
app’s ``static`` directory and pulls all the static files together under
one location, typically a folder at the root of the project.

During deploy, ``manage.py collectstatic --noinput -v 0`` is executed
during the ``__do_collecstatic`` phase. The exact static files directory
is defined by ``settings.STATIC_ROOT``, and the default is named
``staticfiles``.

Since Django Compressor is run after ``collectstatic``, this movement of
``less`` files poses an issue for files that reference relative imports
outside of the app’s ``static`` directory. For instance, ``style``\ ’s
``variables.less`` references ``bootstrap/variables.less``, which is in
the ``node_modules`` directory.

In order to fix the moved references, it is required that
``manage.py fix_less_imports_collectstatic`` is run after
``collectstatic``.

Once you run this, it’s a good idea to regenerate static file
translations with ``manage.py compilejsi18n``.

In short, before testing anything that intends to mimic production
static files. First run:

::

   manage.py collectstatic
   manage.py fix_less_imports_collectstatic
   manage.py compilejsi18n

Compression
-----------

`Django
Compressor <https://django-compressor.readthedocs.org/en/latest/>`__ is
the library we use to handle compilation of ``less`` files and the
minification of ``js`` and compiled ``css`` files.

Compressor blocks are defined inside the
``{% compress css %}{% endcompress %}`` or
``{% compress js %}{% endcompress %}`` blocks in Django templates. Each
block will be processed as one unit during the different steps of
compression.

Best practice is to wrap all script tags and stylesheet links in
compress blocks, in order to reduce file size and number of server
requests made per page.

There are three ways of utilizing Django Compressor’s features:

1. Dev Setup: Server-side on the fly ``less`` compilation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This does not combine any files in compress blocks, and as no effect on
``js`` blocks. This is the default dev configuration.

How is this enabled?
^^^^^^^^^^^^^^^^^^^^

Make sure your ``localsettings.py`` file has the following set:

::

   COMPRESS_ENABLED = False
   COMPRESS_OFFLINE = False

2. Production-like Setup: Compress Offline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pros:

- Closest mirror to production’s setup.
- Easy to flip between Option 2 and Option 3

Cons:

- If you’re doing a lot of front end changes, you have to re-run
  ``collectstatic``, ``fix_less_imports_collectstatic``, and ``compress``
  management commands and restart the server AFTER each change. This will
  be a pain!

NOTE: If you are debugging ``OfflineCompressionError``\ s from
production or staging, you should be compressing offline locally to
figure out the issue.

How to enable?
^^^^^^^^^^^^^^

Do everything from Option 2 for LESS compilers setup.

Have the following set in ``localsettings.py``:

::

   COMPRESS_ENABLED = True
   COMPRESS_OFFLINE = True

Notice that ``COMPRESS_MINT_DELAY``, ``COMPRESS_MTIME_DELAY``, and
``COMPRESS_REBUILD_TIMEOUT`` are not set.

Map Files
---------

``#todo``

CDN
---

A content delivery network or content distribution network (CDN) is a
globally distributed network of proxy servers deployed in multiple data
centers. The goal of a CDN is to serve content to end-users with high
availability and high performance. CDNs serve a large fraction of the
Internet content today, including web objects (text, graphics and
scripts), downloadable objects (media files, software, documents),
applications (e-commerce, portals).

CDN for HQ
~~~~~~~~~~

CommCare HQ uses a CloudFront as CDN to deliver its staticfiles.
CloudFront is configured in the `Amazon
Console <https://us-west-2.console.aws.amazon.com/console/home>`__. You
can find credentials in the dimagi shared keypass under AWS Dev Account.
CloudFront provides us with two URLs. A CDN URL for staging and one for
production. On compilation of the static files, we prefix the static
file with the CloudFront URL. For example:

::

   # Path to static file
   <script src="/static/js/awesome.js"/>
   # This gets converted to
   <script src="<some hash>.cloudfront.net/static/js/awesome.js"/>

When a request gets made to the cloudfront URL, amazon serves the page
from the nearest edge node if it has the file cached. If it doesn’t have
the file, it will go to our server and fetch the file. By default the
file will live on the server for 24 hours.

Cache Busting
~~~~~~~~~~~~~

In order to ensure that the CDN has the most up to date version, we
append a version number to the end of the javascript file that is a sha
of the file. This infrastructure was already in place for cache busting.
This means that awesome.js will actually be rendered as
``awesome.js?version=123``. The CDN recognizes this as a different static file
and then goes to our nginx server to fetch the file.

This cache busting is primarily handled by the ``resource_static``
management command, which runs during deploy. This command hashes the
contents of every static file in HQ and stores the resulting hash codes
in a YAML file, ``resource_versions.yml``. This file is also updated by
the ``build_requirejs`` command during deploy, adding versions for
RequireJS bundle files - these files are auto-generated by
``build_requirejs``, so they don’t exist yet when ``resource_static``
runs. The ``static`` template tag in ``hq_shared_tags`` then handles
appending the version number to the script tag’s ``src``.

Note that this cache busting is irrelevant to files that are contained
within a ``compress`` block. Each compressed block generated a file that
contains a hash in the filename, so there’s no need for the URL
parameter.
