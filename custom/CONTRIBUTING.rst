===================
Writing Custom Code
===================

Code written for an individual project ("custom code") is a sometimes-necessary
evil. We should strive to minimize the use of it, and when it is necessary, be
sure to put in the effort to ensure it can be maintained, understood, and
transferred to other developers. This document is a series of guidelines with
the aim of achieving those goals.

Tests
-----
First and foremost, custom code must be fully verifiable through tests. We must
be able to trust that if the tests pass, the code will work. This will allow
other developers to make repository-wide changes such as large refactors or
library upgrades without risking breaking this code. Custom code is unlikely to
be executed when developers try out their changes locally, or during QA of other
features, so tests provide assurance that it will continue functioning.

A good start, particularly for custom reports, is to request a set of test cases
from the project manager. That is, whoever is writing the spec should be able to
provide some example inputs, such as cases, users, locations, fixtures, and so
forth, as well as the expected result. The developer can then turn this into a
test suite and use that to guide development. As the requirements are changed or
clarified, this test suite should be kept up-to-date and comprehensive enough to
demonstrate that various circumstances are handled correctly.

Writing front-end tests can be difficult due to the difficulties of our
javascript testing infrastructure, which is good at testing pure javascript but
not well-equipped to test interactive UIs within HQ. For this reason, custom UI
work should be minimized, and a manual set of steps for smoke testing any custom
UI work should be provided.

This stricter standard of testing than the rest of the codebase is justified by
the inherent obscurity of custom code.

Providing Context
-----------------
Working with custom code requires project-specific understanding that few
developers will have. The test suite serves to document expectations, which will
help significantly. Further, each custom module should have a ``README`` which
includes links to relevant spec documents and explains at a high level anything
unique to the project, such as unique data models, workflows, or variations from
the norm.

Larger blocks of code that are unique to the project should also be documented.
Smaller units, such as individual functions and lines of code, should ideally be
written clearly enough so as to not require documentation, and should have
comments when that’s not feasible.

While good tests will greatly assist future developers in working with this
code, sometimes it’s necessary to run it in a browser regardless. Custom modules
should include a "bootstrap" management command which creates a domain and all
models necessary to be able to run the code in development environments. This
can share code or db fixtures with the primary test suite. This should allow
other developers to quickly and easily access reports complete with realistic
data when the need arises.

Standardization
---------------
Maintainable code is unsurprising. That means following existing conventions,
patterns, and styles whenever reasonable. The code should pass lint checks and
strive to be as readable as possible, such as by using only short classes,
functions, and methods, limiting the use of inheritance, avoiding duplication,
and generally being as straightforward as possible.

Custom code should be isolated as much as possible from core code. It should
live primarily in a project-specific module in ``custom/``. It can be tied in to
the main codebase by one of the following mechanisms, in rough order of
preference:

#. Using ``DOMAIN_MODULE_MAP`` and registering a ``CUSTOM_REPORTS`` map
#. Using extension points
#. Using a feature flag

The code should be explicit about how and where it is run. It should be
registered in ``DOMAIN_MODULE_MAP``, so it’s clear which domains are expected to
use the code, and it should be restricted to run only on those domains, and on a
specific server environment (or multiple, if necessary).

Support
-------
When custom code is developed by an external contractor, they should have access
to a Dimagi developer for backstopping. This person can answer questions about
how to meet the above requirements, or decide that it’s okay to waive one or
more in some particular circumstance. The contractor should check in regularly
during the development process with the Dimagi developer to ensure the approach
taken is correct. Submitting large amounts of code for monolithic review is
likely to result in a long, painful period of code review. Regular check-ins and
following standardizations can greatly help with this. This Dimagi developer
will share responsibility for the robustness of the code, and so will likely
have extensive input during the review process, though all PR feedback should be
considered, regardless of who provides it.
