/*
    This file does a number of manipulations of global variables that are typically bad practice.
    It does not use strict because it's included everywhere, and strictness is not fully tested.
*/
/* eslint no-implicit-globals: 0 */
/* eslint no-redeclare: 0 */
/* eslint strict: 0 */
/*
 * hqModules provides a poor man's module system for js. It is not a module *loader*,
 * only a module *referencer*: "importing" a module doesn't automatically load it as
 * a script to the page; it must already have been loaded with an explict script tag.
 *
 * Modules MUST have a name, and SHOULD be given the name of the javascript file in
 * which they reside, and SHOULD be themselves simple javascript objects.
 *
 * Define the module. Note that as a convention, the module name should match the file path
 * but exclude the .js extension.
 *   // myapp/static/myapp/js/utils.js
 *   hqDefine('myapp/js/utils', [], function () {
 *      var module = {};
 *      module.util1 = function () {...};
 *      module.util2 = function () {...};
 *      return module;
 *   });
 *
 * Reference the module in another hqDefine module:
 *   // myapp/static/myapp/js/app.js
 *   hqDefine('myapp/js/app', ['myapp/js/utils'], function (utils) {
 *      ...
 *      utils.util1();
 *      ...
 *   });
 */

var COMMCAREHQ_MODULES = {};

/*
 * Transitional version of "define" to handle both RequireJS and non-RequireJS pages.
 * Signature deliberately matches that of "define". On non-RequireJS pages, the dependencies
 * argument is optional, and the major globals ($, ko, _) are available.
 */
function hqDefine(path, dependencies, moduleAccessor) {
    if (arguments.length === 2) {
        return hqDefine(path, [], dependencies);
    }

    (function (factory) {
        var thirdPartyGlobals = {
            'jquery': '$',
            'knockout': 'ko',
            'underscore': '_',
            'clipboard/dist/clipboard': 'ClipboardJS',
            'd3/d3.min': 'd3',
            'ace-builds/src-min-noconflict/ace': 'ace',
            'chai/chai': 'chai',
            'DOMPurify': 'DOMPurify',
            'DOMPurify/dist/purify.min': 'DOMPurify',
            'mocha/mocha': 'mocha',
            'moment/moment': 'moment',
            'crypto-js/crypto-js': 'CryptoJS',
            'hqwebapp/js/lib/modernizr': 'Modernizr',
        };
        if (window.USE_BOOTSTRAP5) {
            thirdPartyGlobals['bootstrap5'] = 'bootstrap';
            thirdPartyGlobals['tempusDominus'] = 'tempusDominus';
        }
        var args = [];
        for (var i = 0; i < dependencies.length; i++) {
            var dependency = dependencies[i];
            if (Object.hasOwn(COMMCAREHQ_MODULES, dependency)) {
                args[i] = COMMCAREHQ_MODULES[dependency];
                if (args[i] === undefined) {
                    throw new Error("The module '" + dependency + "' has not yet been defined.\n\n" +
                        'Did you include <script src="' + dependency + '.js"></script> on your html page?');
                }
            } else if (Object.hasOwn(thirdPartyGlobals, dependency)) {
                args[i] = window[thirdPartyGlobals[dependency]];
            }
        }
        if (!Object.hasOwn(COMMCAREHQ_MODULES, path)) {
            if (path.match(/\.js$/)) {
                throw new Error("Error in '" + path + "': module names should not end in .js.");
            }
            COMMCAREHQ_MODULES[path] = factory.apply(undefined, args);
        } else {
            throw new Error("The module '" + path + "' has already been defined elsewhere.");
        }
    }(moduleAccessor));
}
if (typeof define === 'undefined') {
    define = hqDefine;      // eslint-disable-line no-global-assign
}
