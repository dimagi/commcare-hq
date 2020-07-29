"""
CommCare Extensions
===================

This document describes the mechanisms that can be used to extend CommCare's functionality. There are a number
of legacy mechanisms that are used which are not described in this document. This document will focus on
the use of pre-defined *extension points* to add functionality to CommCare.

Where to put custom code
------------------------
The custom code for extending CommCare may be part of the main `commcare-hq` repository or it may have its own
repository. In the case where it is in a separate repository the code may be 'added' to CommCare by cloning the
custom repository into the `extensions` folder in the root of the CommCare source:

::

    /commcare-hq
      /corehq
      /custom
      ...
      /extensions
        /custom_repo
          /custom
            /app1/models.py
            /app2/models.py

The code in the custom repository must be contained within the `custom` namespace package (without an
`__init__.py` file). Using this structure the custom code will be available to CommCare with the same package
structure as it is in the custom repository. In the example above the following import statement will work
in CommCare as well as in the custom code:

::

    from custom.app1 models import *

Extensions Points
-----------------
The `corehq/extensions` package provides the utilities to register extension points and their implementations
and to retrieve the results from all the registered implementations.

Create an extension point
~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    from corehq import extensions

    @extensions.extension_point
    def get_things(arg1: int, keyword: bool = False) -> List[str]:
        '''Docs for the extension point'''


Registering an extension point implementation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    from xyz import get_things

    @get_things.extend()
    def some_things(arg1, domain, keyword=False):
        return ["thing2", "thing1"]


Extensions may also be limited to specific domains by passing the list
of domains as a keyword argument (it must be a keyword argument). This is only supported
if the extension point defines a `domain` argument.

::

    from xyz import get_things

    @get_things.extend(domains=["cat", "hat"])
    def custom_domain_things(arg1, domain, keyword=False):
        return ["thing3", "thing4"]


Calling an extension point
~~~~~~~~~~~~~~~~~~~~~~~~~~
An extension point is called as a normal function. Results are
returned as a list with any `None` values removed.

::

    from xyz import get_things

    results = get_things(10, True)
"""

from corehq.extensions.interface import CommCareExtensions

extension_manager = CommCareExtensions()
extension_point = extension_manager.extension_point
