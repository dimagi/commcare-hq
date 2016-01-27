# Couchapps

This app is a collection of couch design documents that are isolated from any
sort of module or code context. This is often useful for stuff like code
organization, syncing the design docs to multiple dbs, or performance (see
below).


## Note on CouchDB

For a more in-depth overview, I recommend @dannyroberts' excellent article:
["What every developer should know about CouchDB"](https://gist.github.com/dannyroberts/8d514fb6460a9f4f0404)

#### Databases
**Problem:**
Couch databases do not distinguish between different document types.  Any views
you write have to interact with every document in that database.

**Solution:**
Store each type of document in a separate database. CommCareHQ has historically
used one monolithic couch database, but we are gradually moving things into
their own databases.  This module's `__init__.py` lets you specify which
databases to sync each design document (and by extention, view) to.

#### Design documents and views
**Problem:**
A design document stores any number of views (and filters, but we rarely use
those).  Changing or deleting a view is considered a change to the design
document, and the whole design document (including all the views) must be
synced.

**Solution:**
Make your design documents as small as possible - usually just one view.
`couchapps` helps facilitate this.


## What this module does

Normal apps (modules) in our codebase  can have a `_design` directory which
defines a design doc. In this directory will be some number of views.

```
- app_manager/
   - _design/
      + filters/
      - views/
         - builds_by_date/
            map.js
            reduce.js
         + saved_app/
         + forms_by_xmlns/
```

This creates a single design doc with three views.  Here's what they might look
like in action:

```python
Application.view("app_manager/builds_by_date", ...)
Application.view("app_manager/saved_app", ...)
# in our hypothetical example, this view works on doc_type "XFormInstance"
Application.view("app_manager/forms_by_xmlns", ...)
```

Because of the limitations mentioned above, you can instead create your views
here, where each directory is a separate design doc.  What that file structure
might look like is:

```
- couchapps/
   - app_builds_by_date
      - views
         - view
            map.js
            reduce.js
   + saved_apps
   + forms_by_xmlns
```

Where the convention `corehq/couchapps/<view name>/views/view/` produces the
following views:

```python
Application.view("app_builds_by_date/view", ...)
Application.view("saved_apps/view", ...)
XFormInstance.view("forms_by_xmlns/view", ...)
```

#### Benefits
With this new structure, you can make a change to `"app_builds_by_date"`
without needing to also reindex `"saved_apps"` and `"forms_by_xmlns"`.

In the example above, the `forms_by_xmlns` view operates on XFormInstance, but
for some reason lives in `app_manager`.  By moving it here, you can explicitly
choose in which dbs to include that view.

Writing `Application.view("app_manager/forms_by_xmlns", ...)` should seem a
little weird to you, because it makes sense for views to be associated with the
doc type they operate on, not the module (if the two disagree).
