/* globals jQuery */
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

function _isRequireJSEnvironment() {
    return typeof define === 'function' && define.amd && window.USE_REQUIREJS;
}

function _looksLikeDeferred(obj) {
    return obj
           && _.isFunction(obj.state)
           && _.contains(["pending", "resolved", "rejected"], obj.state());
}

/*
 * Transitional version of "define" to handle both RequireJS and non-RequireJS pages.
 * Signature deliberately matches that of "define". On non-RequireJS pages, the dependencies
 * argument is optional, and the major globals ($, ko, _) are available.
 */
function hqDefine(path, dependencies, moduleAccessor) {
    if (arguments.length === 2) {
        return hqDefine(path, [], dependencies);
    }

    var thirdParty = {
        'jquery': typeof $ === 'undefined' ? (typeof jQuery === 'undefined' ? undefined : jQuery) : $,
        'jQuery': typeof $ === 'undefined' ? (typeof jQuery === 'undefined' ? undefined : jQuery) : $,
        'knockout': typeof ko === 'undefined' ? undefined : ko,
        'ko': typeof ko === 'undefined' ? undefined : ko,
        'underscore': typeof _ === 'undefined' ? undefined : _,
    };
    (function(factory) {
        if (_isRequireJSEnvironment()) {
            define(path, dependencies, factory);
        } else {
console.log("defining " + path);
            var args = [];
            for (var i = 0; i < dependencies.length; i++) {
                var dependency = dependencies[i];
                if (thirdParty.hasOwnProperty(dependency)) {
                    args[i] = thirdParty[dependency];
                } else if (COMMCAREHQ_MODULES.hasOwnProperty(dependency)) {
                    args[i] = hqImport(dependency);
                } else {
console.log("dependency not yet defined: " + dependency);
                    var deferred = $.Deferred();
                    deferred.then(function(moduleName, moduleResult) {
//debugger;
console.log("resolving " + dependency);
                        COMMCAREHQ_MODULES[moduleName] = moduleResult;
                    });
                    args[i] = deferred;
                    COMMCAREHQ_MODULES[dependency] = deferred;
                }
            }
if (path.match(/alert_user/)) {
    //debugger;
}
            if (!COMMCAREHQ_MODULES.hasOwnProperty(path)) {
                if (path.match(/\.js$/)) {
                    throw new Error("Error in '" + path + "': module names should not end in .js.");
                }
                COMMCAREHQ_MODULES[path] = factory.apply(undefined, args);
            }
            else {
                if (_looksLikeDeferred(COMMCAREHQ_MODULES[path])) {
                    COMMCAREHQ_MODULES[path].resolve(path, factory.apply(undefined, args));
                } else {
                    throw new Error("The module '" + path + "' has already been defined elsewhere.");
                }
            }
        }
    }(moduleAccessor));
}

if (typeof define === 'undefined') {
    define = hqDefine;
}

function hqImport(pathOrModule) {
    var isPath = _.isString(pathOrModule);

    if (_isRequireJSEnvironment()) {
        if (isPath) {
            throw new Error("String path '" + pathOrModule + "' passed to hqImport in a RequireJS environment. Calling code needs to be migrated.");
        }
        return pathOrModule;
    }

    if (isPath) {
        if (COMMCAREHQ_MODULES[pathOrModule] === undefined) {
            throw new Error("The module '" + pathOrModule + "' has not yet been defined.\n\n" +
                'Did you include <script src="' + pathOrModule + '"></script> on your html page?');
        }
        return COMMCAREHQ_MODULES[pathOrModule];
    }

    if (_looksLikeDeferred(pathOrModule)) {
        throw new Error("The imported module appears to still be a promise. Has its script tag been included on your html page?");
    }

    return pathOrModule;
}
