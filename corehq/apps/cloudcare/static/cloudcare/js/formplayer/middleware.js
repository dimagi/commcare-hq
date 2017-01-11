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
    var setScrollableMaxHeight = function() {
        var maxHeight,
            maxHeightForm,
            user = FormplayerFrontend.request('currentUser'),
            debuggerHeight = 0;

        if (user.debuggerEnabled) {
            debuggerHeight = 34;
        }
        maxHeight = ($(window).height() -
            FormplayerFrontend.regions.breadcrumb.$el.height());

        // Max height of the form is the space between the debugger and the breadcrumbs
        maxHeightForm = maxHeight - debuggerHeight;

        $('.scrollable-container').css('max-height', maxHeight + 'px');
        $('.form-scrollable-container').css({
            'min-height': maxHeightForm + 'px',
            'max-height': maxHeightForm + 'px',
        });
    };

    SessionNavigate.Middleware.middlewares = [
        logRouteMiddleware,
        clearFormMiddleware,
        clearVersionInfo,
        setScrollableMaxHeight,
    ];
});
