Overview of Static Files and JavaScript Bundlers
================================================

What are Static Files?
----------------------

Static files include any ``css``, ``js``, and image files that are not
dynamically generated during runtime. ``css`` is typically compiled from
``scss`` (or ``less`` on Bootstrap 3 pages) and minified before server
runtime.

``js`` files are collected, combined, and minified using Webpack,
a JavaScript bundler.  Some pages do
not use a bundler or any structured JavaScript module format,
referred to as No-Bundler Pages. No-Bundler Pages are rare and are being transitioned
to using Webpack as part of the `JS Bundler Migration
<https://github.com/dimagi/commcare-hq/blob/master/docs/js-guide/migrating.rst>`__.`

Image files generally stay as-is. The only "dynamic" images
come from file attachments in our database.

Due to their static natures, the primary objective when working with static files is
to make as few requests as possible to them during page load. We aim to combine
static files into one larger, minified file whenever possible.
Another goal is to ensure that the browser caches the static files when possible
to make subsequent page loads faster.


Why use a javascript bundler?
-----------------------------

We use a bundler for our javascript files to reduce the amount of separate
network requests tags needed for any page load. A bundler, like Webpack,
not only combines the necessary javascript, it minifies the javascript to reduce
its overall size. Additionally, Webpack employs code splitting to split commonly referenced
"chunks" of code into separate collective bundles:

    - ``vendor``: common code that comes ``yarn`` dependencies
    - ``common``: native HQ javascript that is referenced across the whole site
    - "app" bundles: shared code across entry points inside a specific app, e.g. ``hqwebapp``, ``domain``, etc.

This code splitting allows chunks of code shared across entry points to be cached in the browser
once, making subsequent page loads much faster.

What is an entry point?
~~~~~~~~~~~~~~~~~~~~~~~

An "entry point" is the starting point or root file for a given page that Webpack uses to
build the dependency graph and generate the output bundle(s).

There is only **one** entry point per page. Multiple pages may share the same entry points; however, there
should never be more than one entry point on a single page.


How do I develop with a JavaScript bundler?
-------------------------------------------

To build Webpack locally for continuous development, run the ``yarn dev`` command.

This command first runs
``webpack/generateDetails.js`` to scan all template files for ``js_entry`` template tags,
identifying Webpack entry points. It then builds Webpack bundles based on the ``webpack/webpack.dev.js``
configuration.

``yarn dev`` can be left running, as it will watch existing entry points for any changes and rebuild
Webpack bundles as needed.

When adding new entry points, please remember to restart ``yarn dev``.

When deploying CommCare HQ, ``yarn build`` is used instead of ``yarn dev``. The primary differences are:

- minification of bundles
- a different algorithm for source maps that is better with minified files but takes longer to generate
- appending filenames with content hashes of files for cache busting purposes

To troubleshoot production-related Webpack issues, you can run ``yarn build`` locally.

Developing on No-Bundle pages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are still some very old sections of the codebase that are not under the jurisdiction of a JavaScript bundler.
These pages can be developed without needing ``yarn dev`` to run in the background. However, you should pay special
attention to your ``localsettings`` setup for Django Compressor, which is explained in the `Compression
<#compression>`__
section below.

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
the library we use to handle compilation of ``scss`` (and ``less``) files and the
minification of no-bundler ``js`` and compiled ``css`` files.

Compressor blocks are defined inside the
``{% compress css %}{% endcompress %}`` or
``{% compress js %}{% endcompress %}`` blocks in Django templates. Each
block will be processed as one unit during the different steps of
compression.

Best practice is to wrap all script tags and stylesheet links in
compress blocks, in order to reduce file size and number of server
requests made per page.

There are three ways of utilizing Django Compressor’s features:

1. Dev Setup: Server-side on the fly ``scss`` compilation
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

A Note on Webpack and Cache Busting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Webpack has its own built-in Cache Busting capabilities which are activated
with the ``webapck/webpack.prod.js`` configuration. This is run during
``yarn build``. Bundles generated by Webpack are then appended with that file's
content cache in order to bust the cache.

In order to run build Webpack locally in the same way as you would in a production
environment, you can run ``yarn build`` instead of ``yarn dev``.
