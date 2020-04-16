hqDefine('icds/js/manage_hosted_ccz', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/components.ko',    // pagination widget
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
                'app_name',
                'app_version_tag',
                'file_name',
                'link_name',
                'note',
                'profile_name',
                'status',
                'version',
            ]);
            var self = {
                id: options.id,
                appName: options.app_name,
                appVersionTag: options.app_version_tag,
                fileName: options.file_name,
                link_name: options.link_name,
                profileName: options.profile_name,
                note: options.note,
                status: options.status,
                version: options.version,
            };
            self.removeUrl = initialPageData.reverse("remove_hosted_ccz", self.id);
            self.recreateUrl = initialPageData.reverse("recreate_hosted_ccz", self.id);
            self.viewUrl = initialPageData.reverse("hosted_ccz", self.link_name);
            return self;
        };
        var hostedCCZsView = function (options) {
            assertProperties.assertRequired(['url']);

            var self = {};
            self.hostings = ko.observableArray();

            // Search options
            self.linkId = ko.observable();
            self.appId = ko.observable();
            self.version = ko.observable();
            self.profileId = ko.observable();
            self.status = ko.observable();

            // Pagination
            self.itemsPerPage = ko.observable(5);
            self.totalItems = ko.observable();
            self.showPaginationSpinner = ko.observable(false);
            self.currentPage = ko.observable(1);
            self.goToPage = function (page) {
                self.showPaginationSpinner(true);
                self.currentPage(page);
                $.ajax({
                    url: options.url,
                    data: {
                        page: page,
                        limit: self.itemsPerPage(),
                        link_id: self.linkId(),
                        app_id: self.appId(),
                        version: self.version(),
                        profile_id: self.profileId(),
                        status: self.status(),
                    },
                    success: function (data) {
                        self.showPaginationSpinner(false);
                        self.hostings(_.map(data.hostings, hostedCCZ));
                        self.totalItems(data.total);
                    },
                });
            };

            self.search = function () {
                self.goToPage(1);
            };

            self.clear = function () {
                self.linkId('');
                self.appId('');
                self.version('');
                self.profileId('');
                self.status('');

                // select2s need to have a change triggered to reflect value in UI
                $("#id_link_id, #id_app_id, #id_version").trigger("change.select2");

                self.goToPage(1);
            };

            self.goToPage(1);

            return self;
        };

        $("#manage-ccz-hostings").koApplyBindings(hostedCCZsView({
            url: initialPageData.reverse('ccz_hostings_json'),
        }));
    });
});
