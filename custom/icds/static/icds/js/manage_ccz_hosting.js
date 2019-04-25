hqDefine('icds/js/manage_ccz_hosting', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'translations/js/app_translations',
], function (
    $,
    ko,
    _,
    initialPageData
) {
    'use strict';
    $(function () {
        var cczHosting = function (id, link, appName, version) {
            var self = {};
            self.link = link;
            self.appName = appName;
            self.version = version;
            self.url = initialPageData.reverse("remove_ccz_hosting", id);
            return self;
        };
        var cczHostingsView = function (hostings) {
            var self = {};
            self.hostings = _.map(hostings, function (hosting) {
                return cczHosting(hosting.id, hosting.link_name, hosting.app_name, hosting.version);
            });
            self.search = function () {
                var linkId = $("#link-id-select").val();
                var appId = $("#app-id-search-select").val();
                var version = $("#version-input").val() || '';
                window.location.search = ("link_id=" + linkId + "&app_id=" + appId + "&version=" +
                    version);
            };
            self.clear = function () {
                window.location.search = "";
            };
            return self;
        };
        $("#manage-ccz-hostings").koApplyBindings(cczHostingsView(initialPageData.get("ccz_hostings")));
    });
});