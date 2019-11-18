# Static Files

Static files include any `css`, `js`, and image files that are not dynamically generated during runtime. `css` is typically compiled from `less` and minified prior to server runtime. `js` files are collected, combined, and minified prior to server runtime. As of this writing we don't compile our JavaScript from a higher level scripting language. Image files generally stay as-is. The only 'dynamic' images come from file attachments in our database.

Due to their static natures, the primary objective for static files is to make as few requests to them during page load, meaning that our goal is to combine static files into one larger, minified file when possible. An additional goal is to ensure that the browser caches the static files it is served to make subsequent page loads faster.

## Collectstatic

Collectstatic is a Django management command that combs through each app's `static` directory and pulls all the static files together under one location, typically a folder at the root of the project.

During deploy, `manage.py collectstatic --noinput -v 0` is executed during the `__do_collecstatic` phase. The exact static files directory is defined by `settings.STATIC_ROOT`, and the default is named `staticfiles`.

Since Django Compressor is run after `collectstatic`, this movement of `less` files poses an issue for files that reference relative imports outside of the app's `static` directory. For instance, `style`'s `variables.less` references `bootstrap/variables.less`, which is in the `bower_components` directory.

In order to fix the moved references, it is required that
`manage.py fix_less_imports_collectstatic` is run after `collectstatic`.

Once you run this, it's a good idea to regenerate static file translations with `manage.py compilejsi18n`.

In short, before testing anything that intends to mimic production static files. First run:

```
manage.py collectstatic
manage.py fix_less_imports_collectstatic
manage.py compilejsi18n
```

## Compression

[Django Compressor](https://django-compressor.readthedocs.org/en/latest/) is the library we use to handle compilation of `less` files and the minification of `js` and compiled `css` files.

Compressor blocks are defined inside the `{% compress css %}{% endcompress %}` or `{% compress js %}{% endcompress %}` blocks in Django templates. Each block will be processed as one unit during the different steps of compression.

Best practice is to wrap all script tags and stylesheet links in compress blocks, in order to reduce file size and number of server requests made per page.

There are three ways of utilizing Django Compressor's features:

### 1. Client side js-based `less` compilation.

This does not combine any files in compress blocks, and as no effect on `js` blocks. This is the default dev configuration.

Pros:
- Don't need to install anything / manage different less versions.

Cons:
- Slowest option, as caching isn't great and for pages with a lot of imports,
things get REAL slow. Plus if you want to use any javascript compilers like
`coffeescript` in the future, this option won't take care of compiling that.
- Is the furthest away from the production environment possible.

#### How is this enabled?

Make sure your `localsettings.py` file has the following set:
```
LESS_DEBUG = True
LESS_WATCH = True  # if you want less.js to watch for changes and compile on the fly!
COMPRESS_ENABLED = False
COMPRESS_OFFLINE = False
```

### 2. On-the-fly server-side compression, with the cache refreshed as changes are made.

Pros:
- Faster than client-side compilation
- Closer to production setup (so you find compressor errors as they happen)
- Can use other features of django compressor (for javascript!)

Cons:
- Have to install multiple less versions (will not apply once we are fully migrated to Bootstrap 3).

#### How is this enabled?
Make sure your `localsettings.py` file has the following set:
```
LESS_DEBUG = False
LESS_WATCH = False
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = False

COMPRESS_MINT_DELAY = 30
COMPRESS_MTIME_DELAY = 3  # set to higher or lower depending on how often you're editing static files
COMPRESS_REBUILD_TIMEOUT = 6000
```

##### Compressor and Caching

If you're doing a lot of front end work (CSS AND/OR Javascript in Bootstrap 3)
and don't want to guess whether or not the cache picked up your changes, set the
following in `localsettings.py`:
```
COMPRESS_MINT_DELAY = 0
COMPRESS_MTIME_DELAY = 0
COMPRESS_REBUILD_TIMEOUT = 0
```

#### Slow JS Compression

If pageloads feel a bit sluggish on your development machine and you don't need to rely on a javascript map to debug something, add this to your `localsettings.py` to use the default JS compressor.

```
COMPRESS_JS_COMPRESSOR = 'compressor.js.JsCompressor'
```

#### How to install multiple LESS compilers to run compressor on `less` files

NOTE: This is only relevant while we are running two versions of Bootstrap. See the main [Commcare-hq readme](https://github.com/dimagi/commcare-hq/blob/master/README.md#install-less) for instructions.

### 3. Compress Offline

Pros:
- Closest mirror to production's setup.
- Easy to flip between Option 2 and Option 3

Cons:
- If you're doing a lot of front end changes, you have to re-run `collectstatic`, `fix_less_imports_collectstatic`, and `compress` management commands and restart the server AFTER each change. This will be a pain!

NOTE: If you are debugging `OfflineCompressionError`s from production or staging, you should be compressing offline locally to figure out the issue.

##### How to enable?

Do everything from Option 2 for LESS compilers setup.

Have the following set in `localsettings.py`:
```
LESS_DEBUG = False
LESS_WATCH = False
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True
```

Notice that `COMPRESS_MINT_DELAY`, `COMPRESS_MTIME_DELAY`, and
`COMPRESS_REBUILD_TIMEOUT` are not set.

## Map Files

`#todo`

## CDN

A content delivery network or content distribution network (CDN) is a globally distributed network of proxy servers deployed in multiple data centers. The goal of a CDN is to serve content to end-users with high availability and high performance. CDNs serve a large fraction of the Internet content today, including web objects (text, graphics and scripts), downloadable objects (media files, software, documents), applications (e-commerce, portals).

### CDN for HQ

CommCareHQ uses a CloudFront as CDN to deliver its staticfiles. CloudFront is configured in the [Amazon Console](https://us-west-2.console.aws.amazon.com/console/home). You can find credentials in the dimagi shared keypass under AWS Dev Account. CloudFront provides us with two URLs. A CDN URL for staging and one for production. On compilation of the static files, we prefix the static file with the CloudFront URL. For example:

```
# Path to static file
<script src="/static/js/awesome.js"/>
# This gets converted to
<script src="<some hash>.cloudfront.net/static/js/awesome.js"/>
```
When a request gets made to the cloudfront URL, amazon serves the page from the nearest edge node if it has the file cached. If it doesn't have the file, it will go to our server and fetch the file. By default the file will live on the server for 24 hours.

### Cache Busting

In order to ensure that the CDN has the most up to date version, we append a version number to the end of the javascript file that is a sha of the file. This infrastructure was already in place for cache busting. This means that awesome.js will actually be rendered as awesome.js?version=<some hash>. The CDN recognizes this as a different static file and then goes to our nginx server to fetch the file.

This cache busting is primarily handled by the `resource_static` management command, which runs during deploy. This command hashes the contents of every static file in HQ and stores the resulting hash codes in a YAML file, `resource_versions.yaml`. This file is also updated by the `build_requirejs` command during deploy, adding versions for RequireJS bundle files - these files are auto-generated by `build_requirejs`, so they don't exist yet when `resource_static` runs. The `static` template tag in `hq_shared_tags` then handles appending the version number to the script tag's `src`.

Note that this cache busting is irrelevant to files that are contained within a `compress` block. Each compressed block generated a file that contains a hash in the filename, so there's no need for the URL parameter.
