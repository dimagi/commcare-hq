## About

We are using a custom build of CK Editor 4 with the plugins mentioned [here](#ck-editor-online-build). There are two ways to create this build:
- **Use CK Editor online builder** - This is the recommended option **if no patches are required**. Note that recreating the build this way automatically downloads the latest version of CK Editor.
- **Build from source** - Use this procedure when building with patches that are not yet included in the main line.

> NOTE: **There is one required patch that is not yet addressed in the upstream repo. Hence at present the build is being created from the source.**

See this PR for patch details: https://github.com/ckeditor/ckeditor4/pull/304

## CK Editor Online Build

Go to the [CK build editor](http://ckeditor.com/builder).

### Use the following plugins:
* clipboard (for drag and drop)
* entities
* undo (for change events)
* widget
* [config helper](http://ckeditor.com/addon/confighelper) (for placeholder support)

Alternatively, you can also refer [build-config.js](/lib/ckeditor/build-config.js) to directly download/open the same setup in CKEditor online builder.

### Secondary plugins required as dependencies.
* toolbar (required by: clipboard))
* dialog (required by: clipboard)
* dialog user interface (required by: dialog)
* notification (required by: clipboard)
* ui button (required by : toolbar)

> NOTE: These are automatically included while using the online builder.

## Building from source

The repo [dimagi/ckeditor-dev](https://github.com/dimagi/ckeditor-dev) which is fork of upstream repo is used for creating a build from source using the branch **vellum-build**.
Follow the below steps:
- Clone the repo and checkout the **vellum-build** branch.
- In case of **updating to the new released version** of CK Editor or any patches, merge the changes on this branch.
  You can add the upstream repo locally using 
  `git remote add upstream https://github.com/ckeditor/ckeditor4.git`
- Download the minimalist skin (v1.0) and unzip/place it in the ./skins
  directory.
- Download confighelper plugin (v1.10.1) and unzip/place it in the ./plugins
  directory.
- Copy the file **vellum/lib/ckeditor/build-config.js** into **./dev/builder**
- Run the command from root directory:  
  ```./dev/builder/build.sh --no-tar```
- Move **vellum/lib/ckeditor/** out of the way.
- Unzip .**/dev/builder/release/ckeditor_dev.zip** into **vellum/lib/ckeditor/**
- Copy below files from old **vellum/lib/ckeditor/** into new unzipped dir:
  - dimagi-README.md
  - build-config.js
- Delete extra plugins from **vellum/lib/ckeditor/plugins**.
- Delete extra skins from **vellum/lib/ckeditor/skins**.

> NOTE: Feel free to use more recent versions of minimalist skin and confighelper plugin if that makes sense.
