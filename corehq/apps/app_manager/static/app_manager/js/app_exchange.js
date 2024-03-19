"use strict";
hqDefine("app_manager/js/app_exchange", [
    "jquery",
    "knockout",
    'analytix/js/kissmetrix',
    "hqwebapp/js/bootstrap3/widgets",  // hqwebapp-select2 for versions
], function (
    $,
    ko,
    kissmetrics
) {
    var AppExchangeModel = function () {
        var self = {};

        self.showVersions = ko.observable(false);

        self.versionButtonText = ko.computed(function () {
            if (self.showVersions()) {
                return gettext("Hide Past Versions");
            }
            return gettext("See Past Versions");
        });

        self.toggleVersions = function () {
            self.showVersions(!self.showVersions());
        };

        return self;
    };

    $(function () {
        $("#hq-content").koApplyBindings(AppExchangeModel());

        $('.import-button').on('click', function () {
            var $tile = $(this).closest(".well");
            kissmetrics.track.event("COVID App Library: Imported application", {
                app_id: $tile.find("[name='from_app_id']").val(),
                app_name: $tile.find(".app-name").text(),
            });
        });
    });
});
