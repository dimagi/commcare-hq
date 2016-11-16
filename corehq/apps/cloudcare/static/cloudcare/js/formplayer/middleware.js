/*global FormplayerFrontend */

FormplayerFrontend.module("SessionNavigate", function (SessionNavigate, FormplayerFrontend, Backbone, Marionette) {
    SessionNavigate.Middleware = {
        apply: function(api) {
            var wrappedApi = {};
            _.each(api, function(value, key) {
                wrappedApi[key] = function() {
                    _.each(SessionNavigate.Middleware.middlewares, function(fn) {
                        fn.call(null, key);
                    });
                    return value.apply(null, arguments);
                };
            });
            return wrappedApi;
        },
    };
    var logRouteMiddleware = function(name) {
        window.console.log('User navigated to ' + name);
    };
    var clearFormMiddleware = function(name) {
        FormplayerFrontend.trigger("clearForm");
    };
    var clearVersionInfo = function(name) {
        FormplayerFrontend.trigger('setVersionInfo', '');
    };

    SessionNavigate.Middleware.middlewares = [
        logRouteMiddleware,
        clearFormMiddleware,
        clearVersionInfo,
    ];
});
