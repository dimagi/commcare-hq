# Application terminology

For any given application, there are a number of different documents.

The primary application document is an instance of `Application`.  This
document's id is what you'll see in the URL on most app manager pages. Primary
application documents should have `copy_of == None` and `is_released ==
False`. When an application is saved, the field `version` is incremented.

When a user makes a build of an application, a copy of the primary
application document is made. These documents are the "versions" you see on
the deploy page. Each build document will have a different id, and the
`copy_of` field will be set to the ID of the primary application document.
Additionally, some attachments such as `profile.xml` and `suite.xml` will be
created and saved to the build doc (see `create_all_files`).

When a build is starred, this is called "releasing" the build.  The parameter
`is_released` will be set to True on the build document.

You might also run in to "remote" applications and applications copied to be
"published on the exchange", but those are quite infrequent.
