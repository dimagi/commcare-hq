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
 * Define the module. Note that as a convention, the module name should match the file path
 * but exclude the .js extension.
 *   // myapp/static/myapp/js/utils.js
 *   hqDefine('myapp/js/utils', function () {
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
 *   var utils = hqImport('myapp/js/utils');
 *   ... utils.util1() ...
 *   ... utils.util2() ...
 *
 * You can also use the following idiom to effectively import only one property or
 * function:
 *
 *   var util1 = hqImport('myapp/js/utils').util1;
 */

var COMMCAREHQ_MODULES = {};

function hqDefine(path, dependencies, moduleAccessor) {
    if (arguments.length === 2) {
        return hqDefine(path, [], dependencies);
    }

    (function(factory) {
        if (typeof define === 'function' && define.amd && window.USE_REQUIREJS) {
            define(path, dependencies, factory);
        } else {
            if (typeof COMMCAREHQ_MODULES[path] !== 'undefined') {
                throw new Error("The module '" + path + "' has already been defined elsewhere.");
            }
            if (path.match(/\.js$/)) {
                throw new Error("Error in '" + path + "': module names should not end in .js.");
            }
            COMMCAREHQ_MODULES[path] = factory(jQuery, (typeof ko === 'undefined' ? undefined : ko), _);
        }
    }(moduleAccessor));
}

// Stopgap for modules that are sometimes used by RequireJS and sometimes not, but
// which have not yet been converted to hqDefine. When not on a RequireJS page,
// moduleAccessor gets passed jQuery, knockout, and underscore, in that order.
function hqGlobal(path, dependencies, moduleAccessor) {
    var thirdParty = {
        'jquery': typeof $ === 'undefined' ? (typeof jQuery === 'undefined' ? undefined : jQuery) : $,
        'jQuery': typeof $ === 'undefined' ? (typeof jQuery === 'undefined' ? undefined : jQuery) : $,
        'knockout': typeof ko === 'undefined' ? undefined : ko,
        'ko': typeof ko === 'undefined' ? undefined : ko,
        'underscore': typeof _ === 'undefined' ? undefined : _,
    };
    (function(factory) {
        if (typeof define === 'function' && define.amd) {
            define(path, dependencies, factory);
        } else {
            var args = [];
            for (var i = 0; i < dependencies.length; i++) {
                var dependency = dependencies[i];
                if (dependency in thirdParty) {
                    args[i] = thirdParty[dependency];
                } else if (dependency in COMMCAREHQ_MODULES) {
                    args[i] = hqImport(dependency);
                }
            }
            if (!(path in COMMCAREHQ_MODULES)) {
                if (path.match(/\.js$/)) {
                    throw new Error("Error in '" + path + "': module names should not end in .js.");
                }
                COMMCAREHQ_MODULES[path] = factory.apply(undefined, args);
            }
        }
    }(moduleAccessor));
}

function hqImport(path) {
    if (typeof COMMCAREHQ_MODULES[path] === 'undefined') {
        throw new Error("The module '" + path + "' has not yet been defined.\n\n" +
            'Did you include <script src="' + path + '"></script> on your html page?');
    }
    return COMMCAREHQ_MODULES[path];
}
