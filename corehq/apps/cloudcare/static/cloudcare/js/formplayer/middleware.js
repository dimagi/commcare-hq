'use strict';
hqDefine("cloudcare/js/formplayer/middleware", function () {
    var FormplayerFrontend = hqImport("cloudcare/js/formplayer/app");

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
            user = FormplayerFrontend.getChannel().request('currentUser'),
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
    var setLastUserActiviyTime = function () {
        sessionStorage.setItem("lastUserActivityTime",  Date.now());
    };

    var self = {};

    self.middlewares = [
        clearFormMiddleware,
        navigationMiddleware,
        clearVersionInfo,
        setScrollableMaxHeight,
        clearBreadcrumbMiddleware,
        setLastUserActiviyTime,
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
