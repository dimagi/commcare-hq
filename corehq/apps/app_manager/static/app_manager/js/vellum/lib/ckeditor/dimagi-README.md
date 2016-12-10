How to recreate
=====

Go to the [CK build editor](http://ckeditor.com/builder).

Use the following plugins:
* clipboard (for drag and drop)
* entities
* floatingspace
* undo (for change events)
* widget
* [config helper](http://ckeditor.com/addon/confighelper) (for placeholder support)

If by chance this hasn't been updated you can also check build-config.js in
lib/ckeditor/


## Building from source

Use this procedure when building with patches that are not yet included in the
main line. Feel free to use more recent version numbers if that makes sense.

- clone https://github.com/millerdev/ckeditor-dev and `cd` into ckeditor-dev
- checkout *widget-nav-4.5.7* branch
- download the minimalist skin (v1.0) and unzip/place it in the ./skins
  directory.
- download confighelper plugin (v1.8.3) and unzip/place it in the ./plugins
  directory
- copy vellum/lib/ckeditor/build-config.js into ./dev/builder
- build: ./dev/builder/build.sh --no-zip --no-tar
- copy ./dev/builder/release/ckeditor/ckeditor.js into vellum/lib/ckeditor/

NOTE: it may be necessary to copy more files from the build output if building
a different version than the one that is currently being used in vellum.
