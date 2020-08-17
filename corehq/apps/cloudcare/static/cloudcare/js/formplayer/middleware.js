/*global FormplayerFrontend */

FormplayerFrontend.module("SessionNavigate", function (SessionNavigate, FormplayerFrontend, Backbone, Marionette) {
    SessionNavigate.Middleware = {
        apply: function (api) {
            var wrappedApi = {};
            _.each(api, function (value, key) {
                wrappedApi[key] = function () {
                    _.each(SessionNavigate.Middleware.middlewares, function (fn) {
                        fn.call(null, key);
                    });
                    return value.apply(null, arguments);
                };
            });
            return wrappedApi;
        },
    };
    var logRouteMiddleware = function (name) {
        window.console.log('User navigated to ' + name);
    };
    var clearFormMiddleware = function (name) {
        FormplayerFrontend.trigger("clearForm");
    };
    var navigationMiddleware = function (name) {
        FormplayerFrontend.trigger("navigation");
    };
    var clearVersionInfo = function (name) {
        FormplayerFrontend.trigger('setVersionInfo', '');
    };
    var clearBreadcrumbMiddleware = function (name) {
        FormplayerFrontend.trigger('clearBreadcrumbs');
    };
    var setScrollableMaxHeight = function () {
        var maxHeight,
            user = FormplayerFrontend.request('currentUser'),
            restoreAsBannerHeight = 0;

        if (user.restoreAs) {
            restoreAsBannerHeight = FormplayerFrontend.regions.getRegion('restoreAsBanner').$el.height();
        }
        maxHeight = ($(window).height() -
            FormplayerFrontend.regions.getRegion('breadcrumb').$el.height() -
            restoreAsBannerHeight);

        $('.scrollable-container').css('max-height', maxHeight + 'px');
        $('.form-scrollable-container').css({
            'min-height': maxHeight + 'px',
            'max-height': maxHeight + 'px',
        });
    };

    SessionNavigate.Middleware.middlewares = [
        logRouteMiddleware,
        clearFormMiddleware,
        navigationMiddleware,
        clearVersionInfo,
        setScrollableMaxHeight,
        clearBreadcrumbMiddleware,
    ];
});
