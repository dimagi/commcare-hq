hqDefine('icds/js/manage_hosted_ccz', [
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
        var hostedCCZ = function (id, link, appName, version, profileName, fileName, note) {
            var self = {};
            self.link = link;
            self.appName = appName;
            self.version = version;
            self.profileName = profileName;
            self.fileName = fileName;
            self.note = note;
            self.url = initialPageData.reverse("remove_hosted_ccz", id);
            self.viewUrl = initialPageData.reverse("hosted_ccz", link);
            return self;
        };
        var hostedCCZsView = function (hostings) {
            var self = {};
            self.hostings = _.map(hostings, function (hosting) {
                return hostedCCZ(hosting.id, hosting.link_name, hosting.app_name, hosting.version,
                    hosting.profile_name, hosting.file_name, hosting.note);
            });
            self.search = function () {
                var linkId = $("#link-id-select").val();
                var appId = $("#app-id-search-select").val();
                var version = $("#version-input").val() || '';
                var profileId = $("#app-profile-id-input").val() || '';
                window.location.search = ("link_id=" + linkId + "&app_id=" + appId + "&version=" +
                    version + "&profile_id=" + profileId);
            };
            self.clear = function () {
                window.location.search = "";
            };
            return self;
        };
        $("#manage-ccz-hostings").koApplyBindings(hostedCCZsView(initialPageData.get("hosted_cczs")));
    });
});
