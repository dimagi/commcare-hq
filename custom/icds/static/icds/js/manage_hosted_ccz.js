hqDefine('icds/js/manage_hosted_ccz', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/initial_page_data',
    'translations/js/app_translations',
], function (
    $,
    ko,
    _,
    assertProperties,
    initialPageData
) {
    'use strict';
    $(function () {
        var hostedCCZ = function (options) {
            assertProperties.assertRequired(options, [
                'id',
                'link',
                'app_name',
                'version',
                'app_version_tag',
                'profile_name',
                'file_name',
                'note',
                'status',
            ]);
            var self = {
                id: options.id,
                link: options.link,
                appName: options.app_name,
                version: options.version,
                appVersionTag: options.app_version_tag,
                profileName: options.profile_name,
                fileName: options.file_name,
                note: options.note,
                status: options.status,
            };
            self.removeUrl = initialPageData.reverse("remove_hosted_ccz", self.id);
            self.recreateUrl = initialPageData.reverse("recreate_hosted_ccz", self.id);
            self.viewUrl = initialPageData.reverse("hosted_ccz", self.link);
            return self;
        };
        var hostedCCZsView = function (hostings) {
            var self = {};
            self.hostings = _.map(hostings, hostedCCZ);
            self.search = function () {
                var linkId = $("#link-id-select").val();
                var appId = $("#app-id-search-select").val();
                var version = $("#version-input").val() || '';
                var profileId = $("#app-profile-id-input").val() || '';
                var status = $("#id_status").val();
                window.location.search = ("link_id=" + linkId + "&app_id=" + appId + "&version=" +
                    version + "&profile_id=" + profileId + "&status=" + status);
            };
            self.clear = function () {
                window.location.search = "";
            };
            return self;
        };
        $("#manage-ccz-hostings").koApplyBindings(hostedCCZsView(initialPageData.get("hosted_cczs")));
    });
});
