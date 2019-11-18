Caching and Memoization
=======================

There are two primary ways of caching in CommCareHQ - using the decorators
``@quickcache`` and ``@memoized``. At their core, these both do the same sort of
thing - they store the results of function, like this simplified version:

.. code-block:: python

    cache = {}

    def get_object(obj_id):
        if obj_id not in cache:
            obj = expensive_query_for_obj(obj_id)
            cache[obj_id] = obj
        return cache[obj_id]


In either case, it is important to remember that the body of the function being
cached is not evaluated at all when the cache is hit. This results in two
primary concerns - what to cache and how to identify it. You should cache only
functions which are referentially transparent, that is, "pure" functions which
return the same result when called multiple times with the same set of
parameters.

This document describes the use of these two utilities.


Memoized
--------

Memoized is an in-memory cache. At its simplest, it's a replacement for the two
common patterns used in this example class:

.. code-block:: python

   class MyClass(object):

       def __init__(self):
           self._all_objects = None
           self._objects_by_key = {}

       @property
       def all_objects(self):
           if self._all_objects is None:
               result = do_a_bunch_of_stuff()
               self._all_objects = result
           return self._all_objects

       def get_object_by_key(self, key):
           if key not in self._objects_by_key:
               result = do_a_bunch_of_stuff(key)
               self._objects_by_key[key] = result
           return self._objects_by_key[key]

With the memoized decorator, this becomes:

.. code-block:: python

   from memoized import memoized

   class MyClass(object):

       @property
       @memoized
       def all_objects(self):
           return do_a_bunch_of_stuff()

       @memoized
       def get_object_by_key(self, key):
           return do_a_bunch_of_stuff(key)

When decorating a class method, ``@memoized`` stores the results of calls to
those methods on the class instance. It stores a result for every unique set of
arguments passed to the decorated function. This persists as long as the class
does (or until you manually invalidate), and will be garbage collected along
with the instance.

You can decorate any callable with ``@memoized`` and the cache will persist for
the life of the callable. That is, if it isn't an instance method, the cache
will probably be stored in memory for the life of the process. This should be
used sparingly, as it can lead to memory leaks. However, this can be useful for
lazily initializing singleton objects. Rather than computing at module load
time:

.. code-block:: python

    def get_classes_by_doc_type():
        # Look up all subclasses of Document
        return result

    classes_by_doc_type = get_classes_by_doc_type()
    
You can memoize it, and only compute if and when it's needed. Subsequent calls
will hit the cache.

.. code-block:: python

    @memoized
    def get_classes_by_doc_type():
        # Look up all subclasses of Document
        return result

Quickcache
----------

``@quickcache`` behaves much more like a normal cache. It stores results in a
caching backend (Redis, in CCHQ) for a specified timeout (5 minutes, by
default). This also means they can be shared across worker machines. Quickcache
also caches objects in local memory (10 seconds, by default). This is faster to
access than Redis, but its not shared across machines.

Quickcache requires you to specify which arguments to "vary on", that is, which
arguments uniquely identify a cache

For examples of how it's used, check out `the repo <repo_>`_. For background,
check out `Why we made quickcache <blog_>`_

.. _repo: https://github.com/dimagi/quickcache
.. _blog: https://www.dimagi.com/blog/why-we-made-quickcache/


The Differences
---------------

Memoized returns the same actual python object that was originally returned by
the function. That is, ``id(obj1) == id(obj2)`` and ``obj1 is obj2``.
Quickcache, on the other hand, saves a copy (however, if you're within the
``memoized_timeout``, you'll get the original object, but don't write code which
depends on it.).

Memoized is a python-only library with no other dependencies; quickcache is
configured on a per-project basis to use whatever cache backend is being used,
in our case django-cache backends.

Incidentally, quickcache also uses some inspection magic that makes it not work
in a REPL context (i.e. from running `python` interactively or `./manage.py
shell`)


Lifecycle
---------

Memoized on instance method:
    The cache lives on the instance itself, so it gets garbage collected along
    with the instance

Memoized on any other function/callable:
    The cache lives on the callable, so if it’s globally scoped and never gets
    garbage collected, neither does the cache

Quickcache:
    Garbage collection happens based on the timeouts specified: memoize_timeout
    for the local cache and timeout for redis


Scope
-----

In-memory caching (memoized or quickcache) is scoped to a single process on a
single machine. Different machines or different processes on the same machine do
not share these caches between them.

For this reason, memoized is usually used when you want to cache things only for
duration of a request, or for globally scoped objects that need to be always
available for very fast retrieval from memory.

Redis caching (quickcache only) is globally shared between processes on all
machines in an environment. This is used to share a cache across multiple
requests and webworkers (although quickcache also provides a short-duration,
lightning quick, in-memory cache like @memoized, so you should never need to use
both).


Decorating various things
-------------------------

Memoized is more flexible here - it can be used to decorate any callable,
including a class. In practice, it’s much more common and practical to limit
ourselves to normal functions, class methods, and instance methods. Technically,
if you do use it on a class, it has the effect of caching the result of calling
the class to create an instance, so instead of creating a new instance, if you
call the class twice with the same arguments, you’ll get the same (`obj1 is
obj2`) python object back.

Quickcache must go on a function—whether standalone or within a class—and does
not work on other callables like a class or other custom callable. In practice
this is not much of a limitation.


Identifying cached values
-------------------------

Cached functions usually have a set of parameters passed in, and will return
different results for different sets of parameters.

Best practice here is to use as small a set of parameters as possible, and to
use simple objects as parameters when possible (strings, booleans, integers,
that sort of thing).

.. code-block:: python

    @quickcache(['domain_obj.name', 'user._id'], timeout=10)
    def count_users_forms_by_device(domain_obj, user):
        return {
            FormAccessors(domain_obj.name).count_forms_by_device(device.device_id)
            for device in user.devices
        }

The first argument to ``@quickcache`` is an argument called ``vary_on`` which is
a list of the parameters used to identify each result stored in the cache. Taken
together, the variables specified in vary_on should constitute all inputs that
would change the value of the output. You may be thinking “Well, isn’t that just
all of the arguments?” Often, yes. However, also very frequently, a function
depends not on the exact object being passed in, but merely on one or a few
properties of that object. In the example above, we want the function to return
the same result when called with the same domain name and user ID, not
necessarily the same exact objects. Quickcache handles this by allowing you to
pass in strings like ``parameter.attribute``. Additionally, instead of a list of
parameters, you may pass in a function, which will be called with the arguments
of the cached function to return a cache key.

Memoized does not provide these capabilities, and instead always uses all of the
arguments passed in. For this reason, you should only memoize functions with
simple arguments. At a minimum, all arguments to memoized must be hashable.
You'll notice that the above function doesn't actually use anything on the
``domain_obj`` other than name, so you could just refactor it to accept
``domain`` instead (this also means code calling this function won't need to
fetch the domain object to pass to this function, only to discard everything
except the name anyways).

You don't need to let this consideration muck up your function's interface. A
common practice is to make a helper function with simple arguments, and decorate
that. You can then still use the top-level function as you see fit. For example,
let's pretend the above function is an instance method and you want to use
memoize rather than quickcache. You could split it apart like this:

.. code-block:: python

    @memoized
    def _count_users_forms_by_device(self, domain, device_id):
        return FormAccessors(domain).count_forms_by_device(device_id)

    def count_users_forms_by_device(self, domain_obj, user):
        return {
            self._count_users_forms_by_device(domain_obj.name, device.device_id)
            for device in user.devices
        }


What can be cached
------------------

Memoized:
    All arguments must be hashable; notably, lists and dicts are not hashable,
    but tuples are.

    Return values can be anything.

Quickcache:
    All vary_on values must be “basic” types (all the way down, if they are
    collections): string types, bool, number, list/tuple (treated as interchangeable),
    dict, set, None. Arbitrary objects are not allowed, nor are
    lists/tuples/dicts/sets containing objects, etc.

    Return values can be anything that’s pickleable. More generally, quickcache
    dictates what values you can vary_on, but leaves what values you can return
    up to your caching backend; since we use django cache, which uses pickle,
    our return values have to be pickleable.


Invalidation
------------

    "There are only two hard problems in computer science - cache invalidation
    and naming things" (and off-by-one errors)

Memoized doesn’t allow invalidation except by blowing away the whole cache for
all parameters. Use ``<function>.reset_cache()``

If you are trying to clear the cache of a memoized `@property`, you will need to
invalidate the cache manually with ``self._<function_name>_cache.clear()``

One of quickcache’s killer features is the ability to invalidate the cache for a
specific function call. To invalidate the cache for ``<function>(*args,
**kwargs)``, use ``<function>.clear(*args, **kwargs)``. Appropriately selecting
your args makes this easier.

To sneakily prime the cache of a particular call with a preset value, you can
use ``<function>.set_cached_value(*args, **kwargs).to(value)``. This is useful
when you are already holding the answer to an expensive computation in your
hands and want to do the next caller the favor of not making them do it. It’s
also useful for when you’re dealing with a backend that has delayed refresh as
is the case with Elasticsearch (when configured a certain way).


Other ways of caching
---------------------

Redis is sometimes accessed manually or through other wrappers for special
purposes like locking. Some of those are:

RedisLockableMixIn
    Provides ``get_locked_obj``, useful for making sure only one instance of an
    object is accessible at a time.

CriticalSection
    Similar to the above, but used in a ``with`` construct - makes sure a block
    of code is never run in parallel with the same identifier.

QuickCachedDocumentMixin
    Intended for couch models - quickcaches the ``get`` method and provides
    automatic invalidation on save or delete.

CachedCouchDocumentMixin
    Subclass of QuickCachedDocumentMixin which also caches some couch views
