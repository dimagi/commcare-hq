/*
 * hqModules provides a poor man's module system for js. It is not a module *loader*,
 * only a module *referencer*: "importing" a module doesn't automatically load it as
 * a script to the page; it must already have been loaded with an explict script tag.
 *
 * Modules MUST have a name, and SHOULD be given then name
 * of the javascript file in which they reside, and
 * SHOULD be themselves simple javascript objects.
 *
 * Modules are defined with hqDefine, and "imported" (referenced) with hqImport. Example:
 *
 * Define the module:
 *   // myapp/static/myapp/js/utils.js
 *   hqDefine('myapp/js/utils.js', function () {
 *      var module = {};
 *      module.util1 = function () {...};
 *      module.util2 = function () {...};
 *      return module;
 *   });
 *
 * Include the module source on your page:
 *   // myapp/templates/myapp/page.html
 *   ...
 *   <script src="myapp/js/utils.js"></script>
 *   ...
 *
 * Reference the module in other code
 * (either directly in the template or in another file/module):
 *
 *   var utils = hqImport('myapp/js/utils.js');
 *   ... utils.util1() ...
 *   ... utils.util2() ...
 *
 * You can also use the following idiom to effectively import
 * only one property or function:
 *
 *   var util1 = hqImport('myapp/js/utils.js').util1;
 */

var COMMCAREHQ_MODULES = {};

function hqDefine(path, moduleAccessor) {
    var parts = path.split('/');
    var i;
    var object = COMMCAREHQ_MODULES;
    for (i = 0; i < parts.length - 1; i += 1) {
        if (typeof object[parts[i]] === 'undefined') {
            object[parts[i]] = {};
        }
        object = object[parts[i]];
    }
    if (typeof object[parts[i]] !== 'undefined') {
        throw new Error("The module '" + path + "' has already been defined elsewhere.");
    }
    object[parts[i]] = moduleAccessor();
}

function hqImport(path) {
    var parts = path.split('/');
    var i;
    var object = COMMCAREHQ_MODULES;
    for (i = 0; i < parts.length; i += 1) {
        object = object[parts[i]];
    }
    return object;
}
