hqDefine('app_manager/js/manage_releases_by_location', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/assert_properties',
    'locations/js/search',
    'hqwebapp/js/bootstrap3/widgets', // using select2/dist/js/select2.full.min for ko-select2 on location select
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
        var enabledAppRelease = function (details) {
            var self = {};
            assertProperties.assert(details, [], ['id', 'build_id', 'active', 'app', 'version', 'location',
                'activated_on', 'deactivated_on']);
            self.id = details.id;
            self.build_id = details.build_id;
            self.active = ko.observable(details.active);
            self.app = details.app;
            self.version = details.version;
            self.location = details.location;
            self.activatedOn = ko.observable(details.activated_on);
            self.deactivatedOn = ko.observable(details.deactivated_on);
            self.errorMessage = ko.observable();
            self.domId = "restriction_" + self.id;
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
            self.requestUrl = function () {
                if (self.active()) {
                    return initialPageData.reverse('deactivate_release_restriction', self.id);
                }
                return initialPageData.reverse('activate_release_restriction', self.id);
            };
            self.toggleRestriction = function () {
                self.ajaxInProgress(true);
                var oldStatus = self.active();
                $.ajax({
                    method: 'POST',
                    url: self.requestUrl(),
                    success: function (data) {
                        if (data.success) {
                            self.toggleStatus();
                            self.activatedOn(data.activated_on);
                            self.deactivatedOn(data.deactivated_on);
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

        function manageReleasesViewModel(appReleasesByLocation) {
            var self = {};
            self.appReleasesByLocation = ko.observableArray(appReleasesByLocation);
            return self;
        }
        var appReleasesByLocation = _.map(initialPageData.get('app_releases_by_location'), enabledAppRelease);
        var viewModel = manageReleasesViewModel(appReleasesByLocation);
        if (appReleasesByLocation.length) {
            $('#managed-releases').koApplyBindings(viewModel);
        }
        function manageReleaseSearchViewModel() {
            var self = {};
            self.search = function () {
                var appId = $("#app-id-search-select").val();
                var locationId = $("#location_search_select").val();
                var version = $("#version-input").val() || '';
                var status = $("#status-input").val() || '';
                window.location.search = ("location_id=" + locationId + "&app_id=" + appId + "&version=" +
                    version + "&status=" + status);
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
