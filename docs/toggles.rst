Plugins
=======

There are a number of plugins which sit on top of the core CommCare functionality that enable a specific set of functionality. For safety these plugins aren't available to end-users when the platform is hosted for external signups in a multi-tenant configuration, rather these plugins are enabled by system administrators. 

When hosting the CommCare HQ, be aware that plugins aren't fully supported by the core committers and generally have a higher support burden. They may require directly reading the code to provide support or understand in full. A smaller percentage of CommCare’s open source developer community typically has knowledge on any given plugin. If you are enabling plugins in your local environment, please make sure you have sufficient engineering expertise to be able to read direct code-level documentation. Plugins can be managed through the admin UI, available at ``https://<hq.server.url>/hq/flags/``.

The CommCare Community of Practice urges all plugin maintainers to follow our best practices for `documentation <(https://commcare-hq.readthedocs.io/documenting.html>`_. Each commit should include a description of the functionality and links to relevant tickets.

Plugins allow limiting access to a set of functionality.

They are implemented as a couchdb-backed django app, designed to be *simple* and *fast* (automatically cached).

Most plugins are configured by manually adding individual users or domains in the plugins admin UI. These are defined by adding a new ``StaticToggle`` in this file. See ``PredictablyRandomToggle`` and ``DynamicallyPredictablyRandomToggle`` if you need a plugin to be defined for a random subset of users.

Namespaces define the type of access granted. NAMESPACE_DOMAIN allows the plugin to be enabled for individual project spaces. NAMESPACE_USER allows the plugin to be enabled for individual users, with the functionality visible to only that user but on any project space they visit.

NAMESPACE_DOMAIN is preferred for most flags, because it can be confusing for different users to experience different behavior. Domain-based flags are like a lightweight privilege that's independent of a software plan. User-based flags are more like a lightweight permission that's independent of user roles (and therefore also independent of domain).

Tags document the feature's expected audience, particularly services projects versus SaaS projects.

See descriptions below. Tags have no technical effect. When in doubt, use TAG_CUSTOM to limit your plugin's support burden.

When adding a new plugin, define it near related plugins - this file is frequently edited, so appending it to the end of the file invites merge conflicts.

To access your plugin:

- In python, StaticToggle has ``enabled_for_request``, which takes care of detecting which namespace(s) to check,
  and ``enabled``, which requires the caller to specify the namespace.
- For python views, the ``required_decorator`` is useful.
- For python tests, the ``flag_enabled`` decorator is useful.
- In HTML, there's a ``toggle_enabled`` template tag.
- In JavaScript, the ``hqwebapp/js/toggles`` modules provides as ``toggleEnabled`` method.

(Note: Plugins were historically called Feature Flags and Toggles)
