CloudCare
=========

Overview
--------
The goal of this section is to give an overview of the CloudCare system for developers who are new to CloudCare.
It should allow one's first foray into the system to be as painless as possible by giving him or her a high level overview of the system.

Backbone
~~~~~~~~

On the frontend, CloudCare is a single page `backbone.js <http://backbonejs.org/>`_ app. The app, module, form, and case selection
parts of the interface are rendered by backbone while the representation of the form itself is controlled by touchforms (described below).

When a user navigates CloudCare, the browser is not making full page reload requests to our Django server, instead, javascript is used to modify the contents of the page and change the url in the address bar. Whenever a user directly enters a CloudCare url like ``/a/<domain>/cloudcare/apps/<urlPath>`` into the browser, the `cloudcare_main <https://github.com/dimagi/commcare-hq/blob/54ef84a62ba9872a11527dcc6c42c388962ed713/corehq/apps/cloudcare/views.py#L53>`_ view is called. This page loads the backbone app and perhaps bootstraps it with the currently selected app and case.

The Backbone Views
~~~~~~~~~~~~~~~~~~

The backbone app consists of several ``Backbone.View``\ s subclasses. What follows is a brief description of several of the most important classes used in the CloudCare backbone app.

``cloudCare.AppListView``
    Renders the list of apps in the current domain on the left hand side of the page.

``cloudCare.ModuleListView``
    Renders the list of modules in the currently selected app on the left hand side of the page.

``cloudCare.FormListView``
    Renders the list of forms in the currently selected module on the left hand side of the page.

``cloudCareCases.CaseMainView``
    Renders the list of cases for the selected form. Note that this list is populated asynchronously.

``cloudCareCases.CaseDetailsView``
    Renders the table displaying the currently selected case's properties.

``cloudCare.AppView``
    AppView holds the module and form list views.
    It is also responsible for inserting the form html into the DOM.
    This html is constructed using JSON returned by the touchforms process and several js libs
    found in the ``/touchforms/formplayer/static/formplayer/script/`` directory. This is kicked off by the AppView's ``_playForm`` method.
    AppView also inserts ``cloudCareCases.CaseMainView``\ s as necessary.

``cloudCare.AppMainView``
    AppMainView (not to be confused with AppView) holds all of the other views and is the entry point for the application. Most of the applications event handling is set up inside AppMainView's ``initialize`` method. The AppMainView has a router. Event handlers are set on this router to modify the state of the backbone application when the browser's back button is used, or when the user enters a link to a certain part of the app (like a particular form) directly.

Touchforms
----------
The backbone app is not responsible for processing the XFrom.
This is done instead by our XForms player, touchforms.
Touchforms runs as a separate process on our servers, and sends JSON to the backbone application representing the structure of the XForm.
Touchforms is written in jython, and serves as a wrapper around the JavaRosa that powers our mobile applications.
