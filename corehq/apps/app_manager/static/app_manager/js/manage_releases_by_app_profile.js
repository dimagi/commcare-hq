hqDefine('app_manager/js/manage_releases_by_app_profile', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/assert_properties',
    'translations/js/app_translations',
], function (
    $,
    ko,
    _,
    initialPageData,
    assertProperties
) {
    'use strict';
    $(function () {
        var AppRelease = function (details) {
            var self = {};
            assertProperties.assert(details, [], ['app_id', 'active', 'app_name', 'profile_name',
                'version']);
            self.active = details.active;
            self.status = details.active ? gettext('Active') : gettext('Inactive');
            self.app_name = details.app_name;
            self.version = details.version;
            self.profile_name = details.profile_name;
            self.domId = "restriction_" + self.id;
            return self;
        };

        function manageReleasesByAppProfileViewModel(appReleasesByAppProfile) {
            var self = {};
            self.appReleasesByAppProfile = ko.observableArray(appReleasesByAppProfile);
            return self;
        }
        var appReleasesByAppProfile = _.map(initialPageData.get('app_releases_by_app_profile'), AppRelease);
        var viewModel = manageReleasesByAppProfileViewModel(appReleasesByAppProfile);
        if (appReleasesByAppProfile.length) {
            $('#managed-releases').koApplyBindings(viewModel);
        }
        function manageReleaseSearchViewModel() {
            var self = {};
            self.search = function () {
                var appId = $("#app-id-search-select").val();
                var profileId = $("#app-profile-id-input").val() || '';
                var version = $("#version-input").val() || '';
                window.location.search = ("build_profile_id=" + profileId + "&app_id=" + appId + "&version=" +
                    version);
            };
            self.clear = function () {
                window.location.search = "";
            };
            return self;
        }
        var searchViewModel = manageReleaseSearchViewModel();
        $("#manage-app-releases").koApplyBindings(searchViewModel);
    });
});
