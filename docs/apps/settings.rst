Adding a new CommCare Setting
=============================

A new setting can be defined in commcare-app-settings.yml or
commcare-profile-settings.yml depending on whether the setting is HQ
only or should also go to mobile xml files. The spec for setting is
given in below section.

CommCare Settings Config Spec
=============================

This page documents the YAML configuration found in these locations:

-  `commcare-app-settings.yml <https://github.com/dimagi/core-hq/blob/master/corehq/apps/app_manager/static/app_manager/json/commcare-app-settings.yml>`__:
   Settings that are specific to CommCare HQ's configurations
-  `commcare-profile-settings.yml <https://github.com/dimagi/core-hq/blob/master/corehq/apps/app_manager/static/app_manager/json/commcare-profile-settings.yml>`__:
   Settings that are 1-to-1 with CommCare mobile profile features/properties
-  `commcare-settings-layout.yml <https://github.com/dimagi/core-hq/blob/master/corehq/apps/app_manager/static/app_manager/json/commcare-settings-layout.yml>`__:
   Determines how these settings are grouped and laid out on the app settings page

Each of ``commcare-app-settings.yml`` and ``commcare-profile-settings.yml`` contain a yaml list with each element containing the following properties:

Required properties
-------------------

-  ``id`` - The "``key``\ " attribute to be used in the CommCare profile
   (or "feature" name)
-  ``name`` - Human readable name of the property
-  ``description`` - A longer human readable description of what the
   property does
-  ``default`` - The default value for the property
-  ``values`` - All the possible values for the property
-  ``value_names`` - The human readable names corresponding to the
   ``values``

Optional
--------

-  ``requires`` - Should be set if this property is only enabled when
   another property has a certain value. Syntax is
   ``"{SCOPE.PROPERTY}='VALUE'"``, where ``SCOPE`` can be ``hq``,
   ``properties``, ``features``, or ``$parent``.
-  ``requires_txt`` - Optional text explaining the dependency enforced
   by ``requires``
-  ``contingent_default`` - What value to force this property to if it's
   disabled. E.g.
   ``[{"condition": "{features.sense}='true'", "value": "cc-su-auto"}]``,
   means "if the feature ``sense`` is ``'true'``, then this property
   should be forced to take the value ``"cc-su-auto"``.
-  ``since`` - The CommCare version in which this property was
   introduced. E.g. ``2.1``.
-  ``type`` - Less common. To render as a "feature" set this to
   ``"features"``.
-  ``commcare_default`` - The default used by CommCare, if it differs
   from the default we want it to have on HQ.
-  ``disabled_default`` - The default to be used if the app's build
   version is less than the ``since`` parameter. ``contingent_default``
   takes precedence over this setting.
-  ``values_txt`` - Extra help text describing what values can be
   entered
-  ``group`` - Presentational; defines how the properties get grouped on
   HQ
-  ``disabled`` - Set to ``true`` for deprecated values we don't want to
   show up in the UI anymore
-  ``force`` - Set to ``true`` to have the ``force`` attribute of the
   setting set when building the profile. Only applies when
   type='properties' (default).
-  ``toggle`` - If specified, the property will only be shown if the
   given toggle is enabled. The value should be an identifier for a
   toggle in ``corehq/toggles.py``, e.g. ``CUSTOM_APP_BASE_URL``
-  ``warning`` - Text displayed if the value of the setting is invalid


Only static setting options can be defined in settings yaml files, any
app or domain specific context to render the setting on HQ Edit
Application settings page can be provided in
``corehq.apps.app_manager.view.apps:get_app_view_context``

Example
-------

.. code:: yaml

    - name: "Auto Update Frequency"
      description: "How often CommCare mobile should attempt to check for a new, released application version."
      id: "cc-autoup-freq"
      values: ["freq-never", "freq-daily", "freq-weekly"]
      value_names: ["Never", "Daily", "Weekly"]
      default: "freq-never"
      values_txt: "After login, the application will look at the profile's defined reference for the authoritative location of the newest version. This check will occur with some periodicity since the last successful check based on this property. freq-never disables the automatic check."
      since: "1.3"
