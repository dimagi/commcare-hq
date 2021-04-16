Toggles
=======

Toggles, also known as feature flags, allow limiting access to a set of functionality.

They are implemented as a couchdb-backed django app, designed to be *simple* and *fast* (automatically cached).

Most toggles are configured by manually adding individual users or domains in the Feature Flags

admin UI. These are defined by adding a new ``StaticToggle`` in this file. See ``PredictablyRandomToggle``

and ``DynamicallyPredictablyRandomToggle`` if you need a toggle to be defined for a random subset

of users.

Namespaces define the type of access granted. NAMESPACE_DOMAIN allows the toggle to be enabled

for individual project spaces. NAMESPACE_USER allows the toggle to be enabled for individual users,

with the functionality visible to only that user but on any project space they visit.

NAMESPACE_DOMAIN is preferred for most flags, because it can be confusing for different users

to experience different behavior. Domain-based flags are like a lightweight privilege that's

independent of a software plan. User-based flags are more like a lightweight permission that's

independent of user roles (and therefore also independent of domain).

Tags document the feature's expected audience, particularly services projects versus SaaS projects.

See descriptions below. Tags have no technical effect. When in doubt, use TAG_CUSTOM to limit

your toggle's support burden.

When adding a new toggle, define it near related toggles - this file is frequently edited,

so appending it to the end of the file invites merge conflicts.

To access your toggle:

- In python, StaticToggle has ``enabled_for_request``, which takes care of detecting which namespace(s) to check,
  and ``enabled``, which requires the caller to specify the namespace.
- For python views, the ``required_decorator`` is useful.
- For python tests, the ``flag_enabled`` decorator is useful.
- In HTML, there's a ``toggle_enabled`` template tag.
- In JavaScript, the ``hqwebapp/js/toggles`` modules provides as ``toggleEnabled`` method.
