quickcache: caching has never been easier

# Usage
quickcache has an easy default for Django, but it's just as easy to bring your own backend.

BYOB:

```python
quickcache = get_quickcache(cache=my_cache_backend)
```

Django:
```python
quickcache = get_django_quickcache(memoize_timeout=10, timeout=5 * 60)
```

...and then lets you cache any function based on the values of some or all of its params

```python
@quickcache(['name'])
def take_expensive_action(name):
    ...
```

...or any method based on values of the `self` object

```python
class Person(object):
    ...
    @quickcache(['self.id'])
    def look_up_friends(self):
        ...
```

... and when you know you just made the cache stale, you can clear it


```python
person.add_friend()
person.look_up_friends.clear(person)
```

# Examples

- cache a singleton function, refresh every 5 minutes
  ```python
  @quickcache([], timeout=5 * 60)
  def get_config_from_db():
      # ...
  ```

- vary on the arguments of a function
  ```python
  @quickcache(['request.couch_user._rev'], timeout=24 * 60 * 60)
  def domains_for_user(request):
      return [Domain.get_by_name(domain)
              for domain in request.couch_user.domains]
  ```
  now as soon as request.couch_user._rev has changed,
  the function will be recomputed

- skip the cache based on the value of a particular arg
  ```python
  @quickcache(['name'], skip_arg='force')
  def get_by_name(name, force=False):
      # ...
  ```

- skip_arg can also be a function and will receive the save arguments as the function:
  ```python
  def skip_fn(name, address):
      return name == 'Ben' and 'Chicago' not in address

  @quickcache(['name'], skip_arg=skip_fn)
  def get_by_name_and_address(name, address):
      # ...
  ```

# Features

- If you're using the Django default,
  then in addition to caching in the default shared cache,
  quickcache caches in memory for `memoize_timeout` seconds,
  (suggested 10 seconds, conceptually the length of a single request).

- In addition to varying on the arguments and the name of the function,
  quickcache will also make sure to vary
  on the _source code_ of your function.
  That way if you change the behavior of the function, there won't be
  any stale cache when you deploy.

- Can vary on any number of the function's parameters

- Does not by default vary on all function parameters.
  This is because it is not in general obvious what it means
  to vary on an object, for example.

- Allows you to vary on an attribute of an object,
  multiple attrs of the same object, attrs of attrs of an object, etc

- Allows you to pass in a function as the vary_on arg which will get called
  with the same args and kwargs as the function. It should return a list of simple
  values to be used for generating the cache key.

# A note on backends

The Django default uses a two-tier caching backend that caches in memory
as well as in the default shared cache.
This is optimized for multi-worker web code so that within a single request
the object is cached in memory, and across requests the object is cached
in the shared cache.

If you are using your own backend, you can achieve the same effect
using quickcache's cache helpers, `TieredCache` and `CacheWithTimeout`.
If you are rolling your own, you may want to work off the source code in
`quickcache/django_quickcache.py`.

In the examples above, the keyword arguments `timeout` and `memoize_timeout`
are only available on the Django default; when you bring your own backend,
and want to override your system-wide default timeout, the equivalent will be
to override the cache with the `cache` keyword argument. For example,

```python
@quickcache(..., cache=get_my_cache_backend_with_timeout(timeout=TIMEOUT))
```

where `get_my_cache_backend_with_timeout` is a function you define.

# Note on unicode and strings in vary_on

When strings and unicode values are used as vary on parameters they will result in the
same cache key if and only if the string values are UTF-8 or ascii encoded.
e.g.
u'namé' and 'nam\xc3\xa9' (UTF-8 encoding) will result in the same cache key
BUT
u'namé' and 'nam\xe9' (latin-1 encoding) will NOT result in the same cache key
