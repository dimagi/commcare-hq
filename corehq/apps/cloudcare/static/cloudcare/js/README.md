# Web Apps JavaScript

## Overview

The web apps front end is effectively a single-page application (SPA), which is unique in HQ.
It's also the only area of HQ that uses [Backbone](https://backbonejs.org/) and [Marionette](https://marionettejs.com/).
Most of the code was written, or substantially re-written, around 2016.

Web apps is tightly coupled with formplayer, so check out the [formplayer README](https://github.com/dimagi/commcare-hq/blob/master/docs/formplayer.rst). This also means web apps tends to use formplay/mobile/CommCare vocabulary rather than HQ vocabulary: "entities"
instead of "cases", etc.

The code has three major components: form entry, formplayer, and everything else.

### Form Entry

This is the [form_entry directory](https://github.com/dimagi/commcare-hq/tree/master/corehq/apps/cloudcare/static/cloudcare/js/form_entry).

It contains the logic for viewing, filling out, and submitting a form.

This is written in knockout, and it's probably the oldest code in this area.

Major files to be aware of:
* [fullform-ui.js](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cloudcare/static/cloudcare/js/form_entry/fullform-ui.js) defines `Question` and `Container`, the major abstractions used by form definitions. `Container` is the base abstraction for groups and for forms themselves.
* [entrycontrols_full.js](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cloudcare/static/cloudcare/js/form_entry/entrycontrols_full.js) defines `Entry` and its many subclasses, the widgets for entering data. The class hierarchy of entries has a few levels. There's generally an entry for each question type: `SingleSelectEntry`, `TimeEntry`, etc. Appearance attributes can also have their own entries, such as `ComboboxEntry` and `GeoPointEntry`.
* [webformsession.js](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cloudcare/static/cloudcare/js/form_entry/webformsession.js) defines the interaction for filling out a form. Web apps sends a request to formplayer every time a question is answered, so the session manages a lot of asynchronous requests, using a task queue. The session also handles loading forms, loading incomplete forms, and within-form actions like changing the form's language.

Form entry has a fair amount of test coverage. There are entry-specific tests and also tests for webformsession.

### FormplayerFrontend

This is the [formplayer directory](https://github.com/dimagi/commcare-hq/tree/master/corehq/apps/cloudcare/static/cloudcare/js/formplayer).

It contains almost all of the non-form-entry logic in web apps.

This is written using Backbone and Marionette. Backbone is an MVC framework for writing SPAs, and Marionette is a library to simplify writing Backbone views.

`FormplayerFrontend` is the  "application" in this SPA.

#### CommCare Concepts

The major CommCare/HQ concepts FormplayerFrontend deals with are apps, users, menus, and sessions. "Apps" and "users" are the same concepts they are in the rest of HQ, while a "menu" is a UI concept that covers the main web apps screens, and "sessions" means incomplete forms.

It's also useful to be familiar with the `CloudcareURL`, which contains the current state of navigation and is the main interface between `FormplayerFrontend` and formplayer itself.

##### Apps

These are HQ apps. Most of the logic around apps has to do with displaying the home screen of web apps, where you see a tiled list of apps along with buttons for sync, settings, etc.

This home screen has access to a subset set of data each app's couch document, similar but not identical to the "brief apps" used in HQ that are backed by the `applications_brief` couch view.

Once you enter an app, web apps no longer has access to this app document. All app functionality in web apps is designed as it is in mobile, with the feature's configuration encoded in the suite.xml or other application files. That config is then added to a formplayer request and passed back to web apps, typically in a navigation request.

##### Users

These are HQ users, although the model has very few of the many attributes of CouchUser.

Most of the time you're only concerned with the current user, who is accessible by requesting `currentUser` from the FormplayerFrontEnd's channel (see below for more on channels).

The users code also deals with the Login As workflow. Login As is often desribed as "restore as" in the code: the user has a `restoreAs` attribute with the username of the current Login As user, the `RestoreAsBanner` is the yellow banner up top that shows who you're logged in as, and the `RestoreAsView` is the Login As screen. The current Login As user is stored in a cookie so that users do not need to re-Login-As often.

##### Menus

This is where the bulk of new web apps development happens. This contains the actual "menu" screen that lists forms & sub-menus, but it also contains case lists, case details, and case search screens.

[menus/views.js](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cloudcare/static/cloudcare/js/formplayer/menus/views.js) contains the views for case list and case detail, while [views/query.js](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cloudcare/static/cloudcare/js/formplayer/menus/views/query.js) contains the case search view.

##### Sessions

These are incomplete forms. When a user is in form entry, web apps creates an incomplete form in the background and stores the current answers frequently so they can be accessed if the user closes their browser window, etc. These expire after a few days, maybe a week, exact lifespan might be configurable by a project setting. They're accessible from the web apps home screen.

##### CloudcareURL

This contains the current state of navigation. It's basically a js object with getter and setter methods. Most data that needs to be passed to or from formplayer ends up as an attribute of CloudcareURL. It interfaces almost directly with formplayer, and most of its attributes are properties of formplayer's [SessionNavigationBean](https://github.com/dimagi/formplayer/blob/master/src/main/java/org/commcare/formplayer/beans/SessionNavigationBean.java).

CloudcareURL is defined in [formplayer/utils/util.js](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cloudcare/static/cloudcare/js/formplayer/utils/util.js) although it probably justifies its own file.

#### Architectural Concepts

There are a few ways that web apps is architecturally different from most HQ javascript, generally related to it being a SPA and being implemented in Backbone and Marionette.

It's heavily asynchronous, since it's a fairly thin UI on top of formplayer. Want to get the a case's details? Ask formplayer. Want to validate a question? Ask formplayer. Adding functionality? It will very likely involve a formplayer PR.

Web apps is also a relatively large piece of functionality to be controlled by a single set of javascript. It doesn't exactly use globals, but `FormplayerFrontend` is basically a god object, and there's a lot of message passing happening, only some of it namespaced.

##### Persistence

Web apps has only transient data. All persistent data is handled by formplayer and/or HQ. The data that's specific to web apps consists mostly of user-related settings and is handled by the browser: cookies, local storage, or session storage.

The Login As user is stored in a cookie. Local storage is used for the user's display options, which are the settings for language, one question per screen, etc. Session storage is also used to support some location handling and case search workflows.

Note that these methods aren't appropriate for sensitive data, which includes all project data. This makes it challenging to implement features like saved searches.

##### Application

`FormplayerFrontend` is a Marionette [Application](https://marionettejs.com/docs/master/marionette.application.html), which ties together a bunch of views and manages their behavior. It's defined in [formplayer/app.js](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cloudcare/static/cloudcare/js/formplayer/app.js).

For day-to-day web apps development, it's just useful to know that `FormplayerFrontend` controls basically everything, and that the initial hook into its behavior is the `start` event, so we have a `before:start` handler and a `start` handler.

##### Regions

Marionette's [regions](https://marionettejs.com/docs/master/marionette.region.html) are UI containers, defined in the FormplayerFrontend's `before:start` handler.

We rarely touch the region-handling code, which defines the high-level structure of the page: the "main" region, the progress bar, breadcrumbs, and the restore as banner. The persistent case tile also has a region. Most web apps development happens within the `main` region.

It is sometimes useful to know how the breadcrumbs work. The breadcrumbs are tightly tied to formplayer's selections-based navigation. See [Navigation and replaying of sessions](https://github.com/dimagi/commcare-hq/blob/master/docs/formplayer.rst#navigation-and-replaying-of-sessions) for an overview and examples. The breadcrumbs use this same selections array, which corresponds to the "steps" attribute of `CloudcareURL`, with one breadcrumb for each selection.

##### Backbone.Radio and Events

Marionette [integrates with Backbone.Radio](https://marionettejs.com/docs/master/backbone.radio.html) to support a global message bus.

Although you can namespace channels, web apps uses a single `formplayer` channel for all messages, which is accessed using `FormplayerFrontend.getChannel()`. You'll see calls to get the channel and then call `request` to get at a variety of global-esque data, especially the current user. All of these requests are handled by `reply` callbacks defined in `FormplayerFrontend`.

`FormplayerFrontend` also supports events, which behave similarly. Events are triggered directly on the `FormplayerFrontend` object, which defines `on` handlers. We tend to use events for navigation and do namespace some of them with `:`, leading to events like `menu:select`, `menu:query`, and `menu:show:detail`.

Counterintuitively, `showError` and `showSuccess` are implemented differently: `showError` is an event and `showSuccess` is a channel request.

##### Routing and Middleware

Being a SPA, all of web apps' navigation is handled by a javascript router, `Marionette.AppRouter`, which extends Backbone's router. [router.js](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cloudcare/static/cloudcare/js/formplayer/router.js) defines the web apps router.

The router also handles actions that may not sound like traditional navigation in the sense that they don't change which screen the user is on. This includes actions like pagination or searching within a case list.

Other code generally interacts with the router by triggering an event (see above for more on events). Most of `router.js` consists of event handlers that then call the router's API.

Every function in the router's API applies the function defined in [middleware.js](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cloudcare/static/cloudcare/js/formplayer/middleware.js). This is rarely edited. It's where the "User navigated to..." console log messages come from.

#### Tests

There are tests in the `spec` directory. There's decent test coverage for js-only workflows, but not for HTML interaction.

### Everything Else

This is everything not in either the `form_entry` or `formplayer` directory.

#### debugger

This controls the debugger, the "Data Preview" bar that shows up at the bottom of app preview and web apps and lets the user evaluate XPath and look at the form data and the submission XML.

#### preview_app

This contains logic specific to app preview.

There isn't much here: some initialization code and a plugin that lets you scroll by grabbing and dragging the app preview screen.

The app preview and web apps UIs are largely identical, but a few places do distinguish between them, using the `environment` attribute of the current user. Search for the constants `PREVIEW_APP_ENVIRONMENT` and `WEB_APPS_ENVIRONMENT` for examples.

[hq.events.js](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/cloudcare/static/cloudcare/js/formplayer/hq.events.js), although not in this directory, is only really relevant to app preview. It controls the ability to communicate with HQ, which is used for the "phone icons" on app preview: back, refresh, and siwtching between the standard "phone" mode and the larger "tablet" mode.

#### config.js

This controls the UI for the Web Apps Permissions page, in the Users section of HQ.
Web apps permissions are not part of the standard roles and permissions framework. They use their own model, which grants/denies permissions to apps based on user groups.

#### formplayer-inline.js

Inline formplayer is for the legacy "Edit Forms" behavior, which allowed users to edit submitted forms using the web apps UI.
This feature has been a deprecation path for quite a while, largely replaced by data corrections. However, there are still a small number of clients using it for workflows that data corrections doesn't support.

#### util.js

This contains miscellaneous utilities, mostly around error/success/progress messaging:

* Error and success message helpers
* Progress bar: the thin little sliver at the very top of both web apps and app preview
* Error and success messaging for syncing and the "settings" actions: clearing user data and breaking locks
* Sending formplayer errors to HQ so they show up in sentry

It also contains a bunch of code, `injectMarkdownAnchorTransforms` and its helpers, related to some custom feature flags that integrate web apps with external applications.
