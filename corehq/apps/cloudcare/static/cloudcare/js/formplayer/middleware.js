'use strict';
hqDefine("cloudcare/js/formplayer/middleware", [
    'jquery',
    'underscore',
    'cloudcare/js/formplayer/app',
    'cloudcare/js/formplayer/users/models',
], function (
    $,
    _,
    FormplayerFrontend,
    UsersModels
) {
    var clearFormMiddleware = function () {
        FormplayerFrontend.trigger("clearForm");
    };
    var navigationMiddleware = function () {
        FormplayerFrontend.trigger("navigation");
        $(window).scrollTop(0);
    };
    var clearVersionInfo = function () {
        FormplayerFrontend.trigger('setVersionInfo', '');
    };
    var clearBreadcrumbMiddleware = function () {
        FormplayerFrontend.trigger('clearBreadcrumbs');
    };
    var setScrollableMaxHeight = function () {
        var maxHeight,
            user = UsersModels.getCurrentUser(),
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

    var self = {};

    self.middlewares = [
        clearFormMiddleware,
        navigationMiddleware,
        clearVersionInfo,
        setScrollableMaxHeight,
        clearBreadcrumbMiddleware,
    ];

    self.apply = function (api) {
        var wrappedApi = {};
        _.each(api, function (value, key) {
            wrappedApi[key] = function () {
                _.each(self.middlewares, function (fn) {
                    fn.call(null, key);
                });
                return value.apply(null, arguments);
            };
        });
        return wrappedApi;
    };

    return self;
});
