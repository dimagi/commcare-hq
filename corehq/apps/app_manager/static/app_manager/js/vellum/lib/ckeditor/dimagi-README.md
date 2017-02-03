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
- checkout *vellum-build* branch
- download the minimalist skin (v1.0) and unzip/place it in the ./skins
  directory.
- download confighelper plugin (v1.8.3) and unzip/place it in the ./plugins
  directory
- copy vellum/lib/ckeditor/build-config.js into ./dev/builder
- build: ./dev/builder/build.sh --no-tar
- move vellum/lib/ckeditor/ out of the way
- unzip ./dev/builder/release/ckeditor_dev.zip into vellum/lib/ckeditor/
- copy files from old vellum/lib/ckeditor/ into new unzipped dir:
  - dimagi-README.md
  - build-config.js
- delete extra plugins from vellum/lib/ckeditor/plugins
- delete extra skins from vellum/lib/ckeditor/skins
