/* global define, jQuery, ko */
/*
 * hqModules provides a poor man's module system for js. It is not a module *loader*,
 * only a module *referencer*: "importing" a module doesn't automatically load it as
 * a script to the page; it must already have been loaded with an explict script tag.
 *
 * Modules MUST have a name, and SHOULD be given the name of the javascript file in
 * which they reside, and SHOULD be themselves simple javascript objects.
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
 * Reference the module in other code (either directly in the template or in another
 * file/module):
 *
 *   var utils = hqImport('myapp/js/utils.js');
 *   ... utils.util1() ...
 *   ... utils.util2() ...
 *
 * You can also use the following idiom to effectively import only one property or
 * function:
 *
 *   var util1 = hqImport('myapp/js/utils.js').util1;
 */

var COMMCAREHQ_MODULES = {};

function hqDefine(path, dependencies, moduleAccessor) {
    if (arguments.length === 2) {
        return hqDefine(path, [], dependencies);
    }
    path = path.replace(/\.js$/, "");

    (function(factory) {
        if (typeof define === 'function' && define.amd) {
            define(path, dependencies, factory);
        } else {
            path = path + ".js";
            if (typeof COMMCAREHQ_MODULES[path] !== 'undefined') {
                throw new Error("The module '" + path + "' has already been defined elsewhere.");
            }
            COMMCAREHQ_MODULES[path] = factory(jQuery, (typeof ko === 'undefined' ? undefined : ko), _);
        }
    }(moduleAccessor));
}

// Stopgap for modules that are sometimes used by RequireJS and sometimes not, but
// which have not yet been converted to hqDefine. When not on a RequireJS page,
// moduleAccessor gets passed jQuery, knockout, and underscore, in that order.
function hqGlobal(path, dependencies, moduleAccessor) {
    (function(factory) {
        if (typeof define === 'function' && define.amd) {
            define(path, dependencies, factory);
        } else {
            factory(jQuery, (typeof ko === 'undefined' ? undefined : ko), (typeof _ === 'undefined' ? undefined : _));
        }
    }(moduleAccessor));
}

function hqImport(path) {
    path = path.replace(/\.js$/, "");
    path = path + ".js";
    if (typeof COMMCAREHQ_MODULES[path] === 'undefined') {
        throw new Error("The module '" + path + "' has not yet been defined.\n\n" +
            'Did you include <script src="' + path + '"></script> on your html page?');
    }
    return COMMCAREHQ_MODULES[path];
}
