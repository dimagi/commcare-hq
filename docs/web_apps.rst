Web Apps JavaScript
~~~~~~~~~~~~~~~~~~~

This document is meant to orient developers to working with Web Apps. Its primary audience is developers who are familiar with CommCare HQ but not especially familiar with CommCare mobile or formplayer.

The web apps front end is effectively a single-page application (SPA), which is unique in HQ.
It's also the only area of HQ that uses `Backbone <https://backbonejs.org/>`_ and `Marionette <https://marionettejs.com/>`_.
Most of the code was written, or substantially re-written, around 2016.

Web apps is tightly coupled with formplayer, so check out the `formplayer README <https://github.com/dimagi/commcare-hq/blob/master/docs/formplayer.rst>`_. High-level pieces of the system:

- **Web Apps** is a piece of CommCare HQ that allows users to enter data in a web browser, providing a web equivalent to CommCare mobile. Like the rest of HQ, web apps is built on django, but it is much heavier on javascript and lighter on python than most areas of HQ. While it is hosted on HQ, its major "backend" is formplayer.

- `Formplayer <https://github.com/dimagi/formplayer/>`_ is a Java-based service for entering data into XForms. Web apps can be thought of as a UI for this service. In this vein, the bulk of web apps javascript implements a javascript application called "FormplayerFrontend". This makes the word "formplayer" sometimes ambiguous in this document: usually it describes the Java-based service, but it also shows up in web apps code references.

- **CloudCare** is a legacy name for web apps. Web apps code is in the ``cloudcare`` django app. It should not be used in documentation or anything user-facing. It shouldn't be used in code, either, unless needed for consistency. It mostly shows up in filenames and URLs.

The coupling with formplayer also means web apps tends to use formplay/mobile/CommCare vocabulary rather than HQ vocabulary: "entities" instead of "cases", etc.

The code has three major components: form entry, formplayer, and everything else, described in more detail below. But first, let's look at how web apps interacts with related systems.

Anatomy of a Web Apps Feature
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

As an example, consider `registration from the case list <https://confluence.dimagi.com/display/commcarepublic/Minimize+Duplicates+Method+1%3A+Registration+From+the+Case+List>`_:

* A CommCareHQ user goes to the module settings page in app builder and turns on the feature, selecting the registration form they want to be accessible from the case list.

   * This adds a new attribute to their ``Application`` document - specifically, it populates ``case_list_form`` on a ``Module``.

* When the user makes a new build of their app, the app building code reads the ``Application`` doc and writes out all of the application files, including the ``suite.xml``.

   * The module's case list configuration is transformed into a `detail <https://github.com/dimagi/commcare-core/wiki/Suite20#detail>`_ element, which includes an `action <https://github.com/dimagi/commcare-core/wiki/Suite20#action>`_ element that represents the case list form.

* When a Web Apps user clicks the menu's name to access the case list, web apps sends a ``navigate_menu`` request to formplayer that includes a set of ``selections`` (see `navigation and replaying of sessions <https://github.com/dimagi/commcare-hq/blob/master/docs/formplayer.rst#navigation-and-replaying-of-sessions>`_).

   * The formplayer response tells web apps what kind of sceen to display:

      * The ``type`` is ``entities`` which tells web apps to display a case list UI

      * The ``entities`` list contains the cases and their properties

      * The ``actions`` list includes an action for the case list registration form, which tells web apps to display a button at the bottom of the case list with the given label, that when clicked will add the string ``action 0`` to the ``selections`` list and then send formplayer another navigation request, which will cause formplayer to send back a form response for the registration form, which web apps will then display for the user.

Note how generic the concepts web apps deals with are: "entities" can be cases, fixture rows, ledger values, etc. Web apps doesn't know what cases are, and it doesn't know the difference between an action that triggers a case list registration form and an action that triggers a case search.

Development for most new web apps features maps to the steps above, requiring some or all of the following:

+--------------------------------------------------------------+------------------+----------------------------+
|                                                              | Repository       | Language                   |
+==============================================================+==================+============================+
| App manager UI where the the feature is enabled & configured | commcare-hq      | Python / HTML / JavaScript |
+--------------------------------------------------------------+------------------+----------------------------+
| App build logic, typically changes to suite generation       | commcare-hq      | Python                     |
+--------------------------------------------------------------+------------------+----------------------------+
| New model for the configuration                              | commcare-core    | Java                       |
+--------------------------------------------------------------+------------------+----------------------------+
| Formplayer processing to add the new feature to a response   | formplayer       | Java                       |
+--------------------------------------------------------------+------------------+----------------------------+
| Web apps UI for the feature                                  | commcare-hq      | JavaScript / HTML          |
+--------------------------------------------------------------+------------------+----------------------------+
| CommCare Mobile UI for the new feature                       | commcare-android | Java                       |
+--------------------------------------------------------------+------------------+----------------------------+

Not all features have all of these pieces:

* Some features don't require any Java

   * They might use existing flexible configuration, like adding a new appearance attribute value to support a new data entry widget

   * They might rearrange existing constructs in a new way. CommCare supports a much broader set of functionality than what HQ allows users to configure.

* Some features don't get implemented on mobile.

* Some features, like case search, have additional HQ work because they interact with HQ in ways beyond what's described above.

Form Entry
^^^^^^^^^^

This is the `form_entry directory <https://github.com/dimagi/commcare-hq/tree/master/corehq/apps/cloudcare/static/cloudcare/js/form_entry>`_.

It contains the logic for viewing, filling out, and submitting a form.

This is written in knockout, and it's probably the oldest code in this area.

Major files to be aware of:

* `form_ui.js
* <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cloudcare/static/cloudcare/js/form_entry/form_ui.js>`_ defines ``Question`` and ``Container``, the major abstractions used by form definitions. ``Container`` is the base abstraction for groups and for forms themselves.
* `entrycontrols_full.js <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cloudcare/static/cloudcare/js/form_entry/entrycontrols_full.js>`_ defines ``Entry`` and its many subclasses, the widgets for entering data. The class hierarchy of entries has a few levels. There's generally a class for each question type: ``SingleSelectEntry``, ``TimeEntry``, etc. Appearance attributes can also have their own classes, such as ``ComboboxEntry`` and ``GeoPointEntry``.
* `webformsession.js <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cloudcare/static/cloudcare/js/form_entry/webformsession.js>`_ defines the interaction for filling out a form. Web apps sends a request to formplayer every time a question is answered, so the session manages a lot of asynchronous requests, using a task queue. The session also handles loading forms, loading incomplete forms, and within-form actions like changing the form's language.

Form entry has a fair amount of test coverage. There are entry-specific tests and also tests for webformsession.

FormplayerFrontend
^^^^^^^^^^^^^^^^^^

This is the `formplayer directory <https://github.com/dimagi/commcare-hq/tree/master/corehq/apps/cloudcare/static/cloudcare/js/formplayer>`_.

It contains logic for selecting an app, navigating through modules, displaying case lists, and almost everything besides filling out a form.

This is written using Backbone and Marionette. Backbone is an MVC framework for writing SPAs, and Marionette is a library to simplify writing Backbone views.

``FormplayerFrontend`` is the  "application" in this SPA.

CommCare Concepts
=================

The major CommCare/HQ concepts FormplayerFrontend deals with are apps, users, menus, and sessions. "Apps" and "users" are the same concepts they are in the rest of HQ, while a "menu" is a UI concept that covers the main web apps screens, and "sessions" means incomplete forms.

Apps
----

These are HQ apps. Most of the logic around apps has to do with displaying the home screen of web apps, where you see a tiled list of apps along with buttons for sync, settings, etc.

This home screen has access to a subset of data from each app's couch document, similar but not identical to the "brief apps" used in HQ that are backed by the ``applications_brief`` couch view.

Once you enter an app, web apps no longer has access to this app document. All app functionality in web apps is designed as it is in mobile, with the feature's configuration encoded in the form XML or suite.xml. That config is then used to generate the web apps UI and to formulate requests to formplayer.

Users
-----

These are HQ users, although the model has very few of the many attributes of CouchUser.

Most of the time you're only concerned with the current user, who is accessible by requesting ``currentUser`` from the FormplayerFrontEnd's channel (see below for more on channels).

The users code also deals with the Login As workflow. Login As is often desribed as "restore as" in the code: the user has a ``restoreAs`` attribute with the username of the current Login As user, the ``RestoreAsBanner`` is the yellow banner up top that shows who you're logged in as, and the ``RestoreAsView`` is the Login As screen. The current Login As user is stored in a cookie so that users do not need to re-Login-As often.

Menus
-----

This is where the bulk of new web apps development happens. This contains the actual "menu" screen that lists forms & sub-menus, but it also contains case lists, case details, and case search screens.

`menus/views.js <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cloudcare/static/cloudcare/js/formplayer/menus/views.js>`_ contains the views for case list and case detail, while `views/query.js <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cloudcare/static/cloudcare/js/formplayer/menus/views/query.js>`_ contains the case search view.

Sessions
--------

These are incomplete forms - the same incomplete forms workflow that happens on mobile, but on web apps, incomplete forms are created automatically instead of at the user's request. When a user is in form entry, web apps creates an incomplete form in the background and stores the current answers frequently so they can be accessed if the user closes their browser window, etc. These expire after a few days, maybe a week, exact lifespan might be configurable by a project setting. They're accessible from the web apps home screen.

Architectural Concepts
======================

There are a few ways that web apps is architecturally different from most HQ javascript, generally related to it being a SPA and being implemented in Backbone and Marionette.

It's heavily asynchronous, since it's a fairly thin UI on top of formplayer. Want to get the a case's details? Ask formplayer. Want to validate a question? Ask formplayer. Adding functionality? It will very likely involve a formplayer PR.

Web apps is also a relatively large piece of functionality to be controlled by a single set of javascript. It doesn't exactly use globals, but ``FormplayerFrontend`` is basically a god object, and there's a lot of message passing happening, only some of it namespaced.

Persistence
-----------

Web apps has only transient data. All persistent data is handled by formplayer and/or HQ. The data that's specific to web apps consists mostly of user-related settings and is handled by the browser: cookies, local storage, or session storage.

The Login As user is stored in a cookie. Local storage is used for the user's display options, which are the settings for language, one question per screen, etc. Session storage is also used to support some location handling and case search workflows.

Note that these methods aren't appropriate for sensitive data, which includes all project data. This makes it challenging to implement features like saved searches.

Application
-----------

``FormplayerFrontend`` is a Marionette `Application <https://marionettejs.com/docs/master/marionette.application.html>`_, which ties together a bunch of views and manages their behavior. It's defined in `formplayer/app.js <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cloudcare/static/cloudcare/js/formplayer/app.js>`_.

For day-to-day web apps development, it's just useful to know that ``FormplayerFrontend`` controls basically everything, and that the initial hook into its behavior is the ``start`` event, so we have a ``before:start`` handler and a ``start`` handler.

Regions
-------

Marionette's `regions <https://marionettejs.com/docs/master/marionette.region.html>`_ are UI containers, defined in the FormplayerFrontend's ``before:start`` handler.

We rarely touch the region-handling code, which defines the high-level structure of the page: the "main" region, the progress bar, breadcrumbs, and the restore as banner. The persistent case tile also has a region. Most web apps development happens within the ``main`` region.

It is sometimes useful to know how the breadcrumbs work. The breadcrumbs are tightly tied to formplayer's selections-based navigation. See `Navigation and replaying of sessions <https://github.com/dimagi/commcare-hq/blob/master/docs/formplayer.rst#navigation-and-replaying-of-sessions>`_ for an overview and examples. The breadcrumbs use this same selections array, which corresponds to the "steps" attribute of ``CloudcareURL``, with one breadcrumb for each selection.

Backbone.Radio and Events
-------------------------

Marionette `integrates with Backbone.Radio <https://marionettejs.com/docs/master/backbone.radio.html>`_ to support a global message bus.

Although you can namespace channels, web apps uses a single ``formplayer`` channel for all messages, which is accessed using ``FormplayerFrontend.getChannel()``. You'll see calls to get the channel and then call ``request`` to get at a variety of global-esque data, especially the current user. All of these requests are handled by ``reply`` callbacks defined in ``FormplayerFrontend``.

``FormplayerFrontend`` also supports events, which behave similarly. Events are triggered directly on the ``FormplayerFrontend`` object, which defines ``on`` handlers. We tend to use events for navigation and do namespace some of them with ``:``, leading to events like ``menu:select``, ``menu:query``, and ``menu:show:detail``.

Counterintuitively, ``showError`` and ``showSuccess`` are implemented differently: ``showError`` is an event and ``showSuccess`` is a channel request.

Routing, URLs, and Middleware
-----------------------------

As in many SPAs, all of web apps' "URLs" are hash fragments appended to HQ's main cloudcare URL, ``/a/<DOMAIN>/cloudcare/apps/v2/``

Navigation is handled by a javascript router, ``Marionette.AppRouter``, which extends Backbone's router.

Web apps routes are defined in `router.js <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cloudcare/static/cloudcare/js/formplayer/router.js>`_.

Routes **outside** of an application use human-readable short names. For example:

* ``/a/<DOMAIN>/cloudcare/apps/v2/#apps`` is the web apps home screen, which lists available apps and actions like sync.

* ``/a/<DOMAIN>/cloudcare/apps/v2/#restore_as`` is the Login As screen

Routes **inside** an application serialize the ``CloudcareURL`` object.

``CloudcareURL`` contains the current state of navigation when you're in an application. It's basically a js object with getter and setter methods.

Most app-related data that needs to be passed to or from formplayer ends up as an attribute of CloudcareURL. It interfaces almost directly with formplayer, and most of its attributes are properties of formplayer's `SessionNavigationBean <https://github.com/dimagi/formplayer/blob/master/src/main/java/org/commcare/formplayer/beans/SessionNavigationBean.java>`_.

CloudcareURL is defined in `formplayer/utils/util.js <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cloudcare/static/cloudcare/js/formplayer/utils/util.js>`_ although it probably justifies its own file.

URLs using ``CloudcareURL`` are not especially human-legible due to JSON serialization, URL encoding, and the obscurity of the attributes. Example URL for form entry:

``/a/<DOMAIN>/cloudcare/apps/v2/#%7B%22appId%22%3A%226<APP_ID>%22%2C%22steps%22%3A%5B%221%22%2C%22<CASE_ID>%22%2C%220%22%5D%2C%22page%22%3Anull%2C%22search%22%3Anull%2C%22queryData%22%3A%7B%7D%2C%22forceManualAction%22%3Afalse%7D``

The router also handles actions that may not sound like traditional navigation in the sense that they don't change which screen the user is on. This includes actions like pagination or searching within a case list.

Other code generally interacts with the router by triggering an event (see above for more on events). Most of ``router.js`` consists of event handlers that then call the router's API.

Every call to one of the router's API functions also runs each piece of web apps middleware, defined in `middleware.js <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cloudcare/static/cloudcare/js/formplayer/middleware.js>`_. This middleware doesn't do much, but it's a useful place for reset-type logic that should be called on each screen change: scrolling to the top of the page, making sure any form is cleared out, etc. It's also where the "User navigated to..." console log messages come from.

Tests
=====

There are tests in the ``spec`` directory. There's decent test coverage for js-only workflows, but not for HTML interaction.

Everything Else
^^^^^^^^^^^^^^^

This is everything not in either the ``form_entry`` or ``formplayer`` directory.

debugger
========

This controls the debugger, the "Data Preview" bar that shows up at the bottom of app preview and web apps and lets the user evaluate XPath and look at the form data and the submission XML.

preview_app
===========

This contains logic specific to app preview.

There isn't much here: some initialization code and a plugin that lets you scroll by grabbing and dragging the app preview screen.

The app preview and web apps UIs are largely identical, but a few places do distinguish between them, using the ``environment`` attribute of the current user. Search for the constants ``PREVIEW_APP_ENVIRONMENT`` and ``WEB_APPS_ENVIRONMENT`` for examples.

`hq_events.js <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cloudcare/static/cloudcare/js/formplayer/hq_events.js>`_, although not in this directory, is only really relevant to app preview. It controls the ability to communicate with HQ, which is used for the "phone icons" on app preview: back, refresh, and switching between the standard "phone" mode and the larger "tablet" mode.

config.js
=========

This controls the UI for the Web Apps Permissions page, in the Users section of HQ.
Web apps permissions are not part of the standard roles and permissions framework. They use their own model, which grants/denies permissions to apps based on user groups.

formplayer_inline.js
====================

Inline formplayer is for the legacy "Edit Forms" behavior, which allowed users to edit submitted forms using the web apps UI.
This feature has been a deprecation path for quite a while, largely replaced by data corrections. However, there are still a small number of clients using it for workflows that data corrections doesn't support.

util.js
=======

This contains miscellaneous utilities, mostly around error/success/progress messaging:

* Error and success message helpers
* Progress bar: the thin little sliver at the very top of both web apps and app preview
* Error and success messaging for syncing and the "settings" actions: clearing user data and breaking locks
* Sending formplayer errors to HQ so they show up in sentry

It also contains a bunch of code, ``injectMarkdownAnchorTransforms`` and its helpers, related to some custom feature flags that integrate web apps with external applications.
