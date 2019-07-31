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
            assertProperties.assertRequired(details, ['id', 'app_id', 'active', 'app_name', 'profile_name',
                'version']);
            self.id = details.id;
            self.active = ko.observable(details.active);
            self.status = details.active ? gettext('Active') : gettext('Inactive');
            self.appName = details.app_name;
            self.version = details.version;
            self.profileName = details.profile_name;
            self.domId = "restriction_" + self.id;
            self.errorMessage = ko.observable();
            self.ajaxInProgress = ko.observable(false);
            self.actionText = ko.computed(function () {
                return (self.active() ? gettext("Remove") : gettext("Add"));
            });
            self.buttonClass = ko.computed(function () {
                return (self.active() ? "btn-danger" : "btn-success");
            });
            self.toggleStatus = function () {
                self.active(!self.active());
            };
            self.error = ko.observable();
            self.requestUrl = initialPageData.reverse('toggle_release_restriction_by_app_profile', self.id);
            self.toggleRestriction = function () {
                self.ajaxInProgress(true);
                var oldStatus = self.active();
                $.ajax({
                    method: 'POST',
                    url: self.requestUrl,
                    data: {'active': !self.active()},
                    success: function (data) {
                        if (data.success) {
                            self.toggleStatus();
                            self.error(false);
                        } else {
                            self.active(oldStatus);
                            self.errorMessage(data.message);
                        }
                    },
                    error: function () {
                        self.active(oldStatus);
                    },
                    complete: function () {
                        self.ajaxInProgress(false);
                        if (self.active() === oldStatus) {
                            self.error(true);
                        }
                    },
                });
            };
            return self;
        };

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

        var appReleasesByAppProfile = _.map(initialPageData.get('app_releases_by_app_profile'), AppRelease);
        if (appReleasesByAppProfile.length) {
            $('#managed-releases').koApplyBindings({
                'appReleasesByAppProfile': ko.observableArray(appReleasesByAppProfile),
            });
        }
        var searchViewModel = manageReleaseSearchViewModel();
        $("#manage-app-releases").koApplyBindings(searchViewModel);
    });
});
