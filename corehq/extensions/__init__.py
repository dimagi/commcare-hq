"""
CommCare Extensions
===================

This package provides the utilities to register extension points and their implementations
and to call retrieve the results from all the registered implementations.

Create and extension point
--------------------------

::

    from corehq import extensions

    @extensions.extension_point
    def get_things(arg1: int, keyword: bool = False):
        '''Docs for the extension point'''


Registering an extension point implementation
---------------------------------------------

::

    from xyz import get_things

    @get_things.extend()
    def some_things(arg1, keyword=False):
        return ["thing2", "thing1"]


Extensions may also be limited to specific domains by passing the list
of domains as a keyword argument (it must be a keyword argument).

::

    from xyz import get_things

    @get_things.extend(domains=["cat", "hat"])
    def custom_domain_things(arg1, keyword=False):
        return ["thing3", "thing4"]


Calling an extension point
--------------------------
An extension point is called as a normal function throught the `hook` interface. Results are
returned as a list with any `None` values removed.

::

    from corehq import extensions

    results = extensions.hook.get_things(10, True)
"""
from corehq.extensions.interface import CommCareExtensions

extension_manager = CommCareExtensions()
extension_point = extension_manager.extension_point
hook = extension_manager.registry
