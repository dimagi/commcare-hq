define(['module'], function (module) {
    var pieces = module.uri.split('/'),
        baseUrl = pieces.slice(0, pieces.length - 1).join('/') + '/',
        moduleIdPieces = module.id.split('/'),
        moduleId = moduleIdPieces[0],
        isBuilt = module.config().env !== 'development';

    // does RequireJS provide an API that would allow us to get this
    // programmatically?
    var MAIN_COMPONENTS = [
        'vellum/core',
        'vellum/ignoreButRetain',
        'vellum/itemset',
        'vellum/javaRosa',
        'vellum/lock',
        'vellum/uploader',
        'vellum/window'
    ];

    // not working correctly for local modules
    function duplicateModulesAsBundles(config, mainComponents) {
        if (!config.modules) {
            return config;
        }
        config.bundles = {};
        for (var i = 0; i < config.modules.length; i++) {
            var module = config.modules[i],
                include = module.include.slice(0);

            if (include.length === 1 && include[0] === 'main') {
                include = mainComponents;
            }

            for (var j = 0; j < include.length; j++) {
                include[j] = include[j].replace(/^\.\//, baseUrl);
            }

            // Need to append '.js' because if module.name ends up being an
            // absolute URL beginning with /, RequireJS will assume that .js
            // shouldn't be appended.  Should possibly change RequireJS to
            // not do that for bundles, or revisit the need to make absolute
            // URLs (may not be necessary any more with a bunch of changes
            // afterwards).
            config.bundles[module.name + '.js'] = include;
        }
        return config;
    }

    // Prepends baseUrl to appropriate paths in the config, based on the
    // location of this file.
    function makeAbsolute(config) {
        var j, k, i, l;
        if (config.paths) {
            for (j in config.paths) {
                config.paths[j] = baseUrl + config.paths[j];
            }
        }
        if (config.map) {
            for (k in config.map) {
                for (l in config.map[k]) {
                    config.map[k][l] = baseUrl + config.map[k][l];
                }
            }
        }
        if (config.shim) {
            for (k in config.shim) {
                var deps = config.shim[k].deps;
                if (!deps) continue;
                for (i = 0; i < deps.length; i++) {
                    deps[i] = deps[i].replace('!', '!' + baseUrl);
                }
            }
        }
        if (config.packages) {
            for (i = 0; i < config.packages.length; i++) {
                config.packages[i].location = baseUrl + config.packages[i].location;
            }
        }
        if (config.bundles) {
            var bundles = {};
            for (k in config.bundles) {
                bundles[baseUrl + k] = config.bundles[k];
            }
            config.bundles = bundles;
        }
        return config;
    }

    // Trick r.js' AST parser.  HACK.
    var oldConfig = requirejs.config;
    requirejs.config = function (config) {
        if (isBuilt) {
            config = duplicateModulesAsBundles(config, MAIN_COMPONENTS);
        }

        config = makeAbsolute(config);

        //console.log(config);
        oldConfig.call(requirejs, config);
        requirejs.config = oldConfig;
    };

    requirejs.config({
        // For some reason when using the map config as suggested by some of the
        // plugins' documentation, and only when including vellum in another
        // app, it tries to get requirejs-promise instead of
        // requirejs-promise.js, so using packages instead.  This might be a bug
        // that should be reported.
        packages: [
            {
                name: 'less',
                location: '../bower_components/require-less',
                main: 'less.js'
            },
            {
                name: 'css',
                location: '../bower_components/require-css',
                main: 'css.js'
            },
            {
                name: 'text',
                location: '../bower_components/requirejs-text',
                main: 'text.js'
            },
            {
                name: 'tpl',
                location: '../bower_components/requirejs-tpl',
                main: 'tpl.js'
            },
            {
                name: 'json',
                location: '../bower_components/requirejs-plugins/src',
                main: 'json.js'
            }
        ],
        less: {
            logLevel: 1
        },
        paths: {
            'vellum': '.',

            'classy': '../bower_components/classy/classy',
            'codemirror': '../lib/codemirror/xml',
            'codemirrorBase': '../lib/codemirror/codemirror',
            'CryptoJS': '../lib/sha1',
            'diff-match-patch': '../lib/diff_match_patch',
            'jquery': '../bower_components/jquery/jquery',
            'jquery-ui': '../lib/jquery-ui/jquery-ui-1.8.14.custom.min',
            'jquery.jstree': '../lib/jstree/jquery.jstree',
            'jquery.fancybox': '../lib/fancybox/jquery.fancybox-1.3.4',
            'jquery.bootstrap': '../lib/bootstrap',
            'jquery.bootstrap-popout': '../lib/bootstrap-popout',
            'jquery.bootstrap-better-typeahead': '../bower_components/bootstrap-better-typeahead/js/bootstrap-better-typeahead',
            'underscore': '../bower_components/underscore/underscore',
            'XMLWriter': '../bower_components/XMLWriter/XMLWriter',

            // todo: should convert xpath submodule to AMD
            'xpath': '../bower_components/xpath/xpath',
            'xpathmodels': '../bower_components/xpath/models',
            'scheme-number': '../bower_components/xpath/lib/schemeNumber',
            'biginteger': '../bower_components/xpath/lib/biginteger',

            'langCodes': '../bower_components/langcodes/langs.json',

            'save-button': '../lib/SaveButton',

            'yui-base': '../bower_components/MediaUploader/yui-base',
            'yui-uploader': '../bower_components/MediaUploader/yui-uploader',

            'swfobject': '../bower_components/MediaUploader/swfobject',
            'file-uploader': '../bower_components/MediaUploader/hqmedia.upload_controller',
        },
        shim: {
            'classy': {
                exports: 'Class'
            },
            'codemirror': {
                deps: ['codemirrorBase', 'css!../lib/codemirror/codemirror'],
                exports: 'CodeMirror',
            },
            'codemirrorBase': {
                exports: 'CodeMirror'
            },
            'CryptoJS': {
                exports: 'CryptoJS'
            },
            'diff-match-patch': {
                exports: 'diff_match_patch'
            },

            'jquery-ui': {
                deps: ['jquery', 'css!../lib/jquery-ui/redmond/jquery-ui-1.8.14.custom'],
                exports: '$.fn.autocomplete'
            },
            'jquery.jstree': {
                deps: ['jquery', 'css!../lib/jstree/default/style'],
                exports: '$.fn.jstree'
            },
            'jquery.fancybox': {
                deps: ['jquery', 'css!../lib/fancybox/jquery.fancybox-1.3.4'],
                exports: '$.fn.fancybox'
            },
            'jquery.bootstrap': {
                deps: ['jquery'],
                exports: '$.fn.popover'
            },
            'jquery.bootstrap-popout': {
                deps: ['jquery.bootstrap'],
                exports: '$.fn.popout'
            },
            'jquery.bootstrap-better-typeahead': {
                deps: ['jquery.bootstrap']
            },
            'underscore': {
                exports: '_'
            },
            'XMLWriter': {
                exports: 'XMLWriter'
            },
            
            'save-button': {
                deps: ['jquery'],
                exports: 'SaveButton'
            },

            'yui-base': {
                exports: 'YUI'
            },
            'yui-uploader': {
                deps: ['yui-base'],
                exports: 'YUI'
            },
            'swfobject': {
                exports: 'swfobject'
            },
            'file-uploader': {
                deps: ['yui-uploader', 'swfobject', 'underscore', 'jquery'],
                exports: 'HQMediaFileUploadController'
            },

            'xpath': {
                deps: ['xpathmodels'],
                exports: 'xpath'
            },
            'xpathmodels': {
                deps: ['scheme-number'],
                exports: 'xpathmodels'
            },
            'scheme-number': {
                deps: ['biginteger'],
                exports: 'SchemeNumber'
            },
            'biginteger': {
                exports: 'BigInteger'
            }
        },
        /** 
         * An attempt to solve the eternal optimization problem of how to bundle
         * components and dependencies together so they will load the fastest for
         * the most users, given variables such as
         *   - the overhead of an HTTP request
         *   - the browser cache
         *   - the rate of changes to files
         *
         * This is a configuration for the optimizer that's meaningless for the
         * asynchronous loader, but we put it here because we generate the
         * 'bundles' config that is used by the asynchronous loader from it, and
         * it's not possible to represent all of this information using bundles.
         */
        modules: [
            // Build-only dependencies that should be excluded from all built
            // modules
            {
                create: true,
                name: 'exclude',
                include: [
                    'css/normalize',
                    'less/normalize'
                ]
            },
            // Global dependencies that may be already loaded on the page.  If
            // any aren't, then a single file containing them all will be
            // requested once.
            //
            // If bootstrap is already loaded, and you load this bundle,
            // you're going to have a bad time.
            {
                create: true,
                name: 'global-deps',
                include: [
                    'jquery',
                    'jquery-ui',
                    'jquery.bootstrap',
                   
                    // shim plugin dependencies don't get automatically included
                    'css/css!../lib/jquery-ui/redmond/jquery-ui-1.8.14.custom'
                ],
                exclude: [
                    'exclude'
                ]
            },
            // Components (and their dependencies) that can be requested
            // asynchronously after Vellum has already finished loading, because
            // they're not necessary for initial operation.

            // At the moment, this bundle doesn't get used as expected.
            //{
                //create: true,
                //name: 'deferred-components',
                //include: [
                    //// core
                    //'codemirror',
                    //'diff-match-patch',
                    //'CryptoJS',
                    //'vellum/expressionEditor',

                    //// uploader
                    //'file-uploader',

                    //// form
                    //'vellum/writer',
                    //'vellum/exporter'
                //],
                //exclude: [
                    //'exclude',
                    //'global-deps',
                    //// required by things other than the expression editor, ensure
                    //// that they're not bundled here, otherwise separate bundles
                    //// is useless
                    //'xpath',
                    //'vellum/util'
                //]
            //},
            // Local dependencies that don't change often, except for new ones being
            // added.
            {
                create: true,
                name: 'local-deps',
                include: [
                    'underscore',
                    'classy',
                    'jquery.jstree',
                    'jquery.fancybox',
                    'jquery.bootstrap-popout',
                    'jquery.bootstrap-better-typeahead',
                    'save-button',

                    // shim plugin dependencies don't automatically get included
                    'css/css!../lib/codemirror/codemirror',
                    'css/css!../lib/jstree/default/style',
                    'css/css!../lib/fancybox/jquery.fancybox-1.3.4',
                ],
                exclude: [
                    'exclude',
                    'global-deps', 
                    //'deferred-components'
                ]
            },
            // Everything else except main.
            {
                create: true,
                name: 'main-components',
                include: ['main'],
                exclude: [
                    'exclude',
                    'global-deps', 
                    //'deferred-components', 
                    'local-deps'
                ],
                // couldn't get it working with including main itself in the
                // built file
                excludeShallow: [
                    'main'
                ]
            }
        ]
    });

    // If jQuery was loaded before RequireJS, use the existing instance.
    // http://www.manuel-strehl.de/dev/load_jquery_before_requirejs.en.html
    if (window.jQuery) {
        define('jquery', [], function() {
            return jQuery;
        });
        if (jQuery.fn.typeahead) {
            define('jquery.bootstrap', [], function () {});
        }
        if (jQuery.fn.popout) {
            define('jquery.bootstrap-popout', [], function () {});
        }

        if (jQuery.fn.datepicker) {
            define('jquery-ui', [], function () {});
        }
    }
});
