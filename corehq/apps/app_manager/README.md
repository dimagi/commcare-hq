# App manager terminology

## Applications (and builds)

An application typically has many different `Application` documents: 
one for the current/primary/canonical application, plus one for each saved build.
The current app's id is what you'll see in the URL on most app manager pages.
Most pages will redirect to the current app if given the id of an older build,
since saved builds are essentially read-only.

In saved builds, `copy_of` contains the primary app's id, while it's `None` for the primary app itself.
If you need to be flexible about finding primary app's id on an object that might be either an app or a build, use the property [master_id](https://github.com/dimagi/commcare-hq/blob/fd9f7aa24f25093683e17a69bb4a14f44d0e15b7/corehq/apps/app_manager/models.py#L4007).

Within code, "build" should always refer to a saved build,
but "app" is used for both the current app and saved builds.
The ambiguity of "app" is occasionally a source of bugs.

Every time an app is saved, the primary doc's `version` is incremented.
Builds have the `version` from which they were created, which is never updated,
even when a build doc is saved (e.g., the build is released or its build comment is updated).

When a user makes a build of an application, a copy of the primary
application document is made. These documents are the "versions" you see on
the deploy page. Each build document will have a different id, and the
`copy_of` field will be set to the ID of the primary application document.
Both builds and primary docs contain `built_on` and `built_with` information - for a primary
app doc, these fields will match those of the most recent build.
Additionally, a build creates attachments such as `profile.xml` and `suite.xml` and saves then to the build doc (see `create_all_files`).

When a build is released, its `is_released` attribute will be set to `True`.
`is_released` is always false for primary application docs.

## Modules

An application contains one or more modules, which are called "menus" in user-facing text. These modules roughly map to menus when using the app on a device. In apps that use case management, each module is associated with a case type.

Each module has a `unique_id` which is guaranteed unique only within the application.

## Forms

A "form" in HQ may refer to either a form *definition* within an application or a form *submission* containing data. App manager code typically deals with form definitions.

A module contains one or more form definitions. Forms, at their most basic, are collections of questions. Forms also trigger case changes and can be configured in a variety of ways.

Each form has a `unique_id` which is guaranteed unique only within the application.

Forms also have an xml namespace, abbreviated `xmlns`, which is part of the form's XML definition.
Reports match form submissions to form definitions using the xmlns plus the app id, which most apps pass along to
[secure_post](https://github.com/dimagi/commcare-hq/blob/5d9122ad2ba23986e6b4493eee0eab16cbcc868b/corehq/apps/receiverwrapper/views.py#L304).
For reports to identify forms accurately, xmlns must be unique within an app.


Duplicate xmlnses in an app will throw an error when a new version of the app is built. When an app is copied, each form in the copy keeps the same XMLNS as the corresponding form in the original. When a form is copied within an app - or when a user uploads XML using an xmlns already in use by another form in the same app - the new form's xmlns will be set to a new value in [save_xform](https://github.com/dimagi/commcare-hq/blob/170690a2fbf8039365fdca852911b4a57fd70a1e/corehq/apps/app_manager/util.py#L171).

### Exceptions
Linked apps use similar workflows to app copy for creating and pulling. See [docs](https://github.com/dimagi/commcare-hq/tree/master/corehq/apps/linked_domain#linked-applications) for more detail on how they handle form unique ids and xmlnses.

Shadow forms are a variation of advanced forms that "shadow" another form's XML but can have their own settings and
actions. Because they don't have their own XML, shadow forms do not have an xmlns but instead inherit their
source form's xmlns. In reports, submissions from shadow forms show up as coming from their source form.
