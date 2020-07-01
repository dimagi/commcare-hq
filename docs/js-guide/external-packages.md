# External Packages

## Bower

Bower can manage components that contain HTML, CSS, JavaScript, fonts or even image files. Bower doesn’t concatenate or minify code or do anything else - it just installs the right versions of the packages you need and their dependencies.

### Bower packages

Bower packages can be installed from a variety of sources, including a registered bower package (a repo that has a `bower.json` file defined), a Github shorthand (`<user or org>/<repo_name>`), a Github URL, or just a plain URL that points to a javascript file.

When you install a package, it will be installed in a directory called `bower_components`. For example if you were to run `bower install jquery`, you would find a directory `bower_components/jquery`.

### Specifying packages in `bower.json`

To ensure a package gets installed for a project, you must specify it in the `bower.json` file. This is equivalent to the `requirements.txt` file for `pip`. Similar to `pip install` for python, for bower, use `bower update` When specifying a bower package you can use many techniques. Here are a few examples:

```js
// Installs the jquery package at version 1.11.1 to `bower_components/jquery`
"jquery": "1.11.1"

// Because `jquery-other` does not refer to a bower package we must specify it in the
// versioning. Bower will install this package to `bower_components/jquery-other`.
"jquery-other": "jquery#1.2.0"

// This will install jquery from a github hash
"jquery-github": "jquery/jquery#44cb97e0cfc8d3e62bef7c621bfeba6fe4f65d7c"

```

To generalize, an install declaration looks like this:
```
<name>:<package>#<version>
```
Where `<package>` is optional if `<name> == <package>`. A package can be any of these things:


| Type | Example |
|---|---|
| Registered package name | jquery |
| Git endpoint | https://github.com/user/package.git |
| Git shorthand | user/repo |
| URL | http://example.com/script.js |

There are more, but those are the important ones. Find the others [here](http://bower.io/docs/api/#install)

A version can be any of these things:

| Type | Example |
|---|---|
| semver | `#1.2.3` |
| version range | `#~1.2.3` |
| Git tag | `#<git tag>` |
| Git commit | `#<commit sha>` |
| Git branch | `#<branch>` |

### Using bower packages in HQ

To use these packages in HQ you need to find where the js file you are looking for. In the case of jquery, it stores the minified jquery version in `jquery/dist/jquery.min.js`:

```
<script src="{% static 'jquery/dist/jquery.min.js' %}"></script>
```

Note: The `node_modules` bit is intentionally left off the path. Django already knows to look in that folder.
