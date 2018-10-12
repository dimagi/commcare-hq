hqDefine("export/js/export_list_main", function () {
    'use strict';

    /* Angular; to be deprecated */
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get,
        listExportsApp = window.angular.module('listExportsApp', ['hq.list_exports']);
    listExportsApp.config(["$httpProvider", function ($httpProvider) {
        $httpProvider.defaults.xsrfCookieName = 'csrftoken';
        $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';
        $httpProvider.defaults.headers.common["X-CSRFToken"] = $("#csrfTokenContainer").val();
    }]);
    listExportsApp.config(["djangoRMIProvider", function (djangoRMIProvider) {
        djangoRMIProvider.configure(initial_page_data("djng_current_rmi"));
    }]);
    listExportsApp.constant('bulk_download_url', initial_page_data("bulk_download_url"));
    listExportsApp.constant('modelType', initial_page_data("model_type"));
    listExportsApp.constant('staticModelType', initial_page_data("static_model_type"));
    listExportsApp.constant('filterFormElements', {
        emwf_form_filter: function () {
            return $('#id_emwf_form_filter');
        },
        emwf_case_filter: function () {
            return $('#id_emwf_case_filter');
        },
    });
    listExportsApp.constant('filterFormModalElement', function () {
        return $('#setFeedFiltersModal');
    });

    /* Knockout */
    var exportModel = function(options) {
        options.isAutoRebuildEnabled = options.isAutoRebuildEnabled || false;
        options.isDailySaved = options.isDailySaved || false;
        options.emailedExport = options.emailedExport || {};

        var mapping = {
            'copy': ["emailedExport"]
        };
        var self = ko.mapping.fromJS(options, mapping);

        self.isLocationSafeForUser = function () {
            return _.isEmpty(self.emailedExport) || self.emailedExport.isLocationSafeForUser;
        };

        return self;
    };

    var exportListModel = function(options) {
        hqImport("hqwebapp/js/assert_properties").assert(options, ['exports']);

        var self = {};

        self.exports = _.map(options.exports, function (e) { return exportModel(e); });
        self.myExports = _.filter(self.exports, function (e) { return !!e.my_export; });
        self.notMyExports = _.filter(self.exports, function (e) { return !e.my_export; });

        self.sendExportAnalytics = function () {
            hqImport('analytix/js/kissmetrix').track.event("Clicked Export button");
            return true;
        };

        self.setFilterModalExport = function (e) {
            // TODO: test, since this comment isn't going to be true anymore
            // The filterModalExport is used as context for the FeedFilterFormController
            self.filterModalExport = e;
        };

        // Bulk export handling
        self.selectAll = function() {
            _.each(self.exports, function (e) { e.addedToBulk(true); });
        };
        self.selectNone = function() {
            _.each(self.exports, function (e) { e.addedToBulk(false); });
        };
        self.showBulkExportDownload = ko.observable(false);
        self.bulkExportList = ko.observable('');
        _.each(self.exports, function (e) {
            e.addedToBulk.subscribe(function (newValue) {
                // Determine whether or not to show bulk export download button & message
                if (newValue !== self.showBulkExportDownload()) {
                    self.showBulkExportDownload(!!_.find(self.exports, function (e) {
                        return e.addedToBulk();
                    }));
                }

                // Update hidden value of exports to download
                if (self.showBulkExportDownload()) {
                    self.bulkExportList(JSON.stringify(_.map(_.filter(self.exports, function (e) {
                        return e.addedToBulk();
                    }), function (e) {
                        return ko.mapping.toJS(e);
                    })));
                }
            });
        });

        return self;
    };

    $(function () {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data");

        $("#create-export").koApplyBindings(hqImport("export/js/create_export").createExportModel({
            model_type: initialPageData.get("model_type", true),
            drilldown_fetch_url: initialPageData.reverse('get_app_data_drilldown_values'),
            drilldown_submit_url: initialPageData.reverse('submit_app_data_drilldown_form'),
            page: {
                is_daily_saved_export: initialPageData.get('is_daily_saved_export', true),
                is_feed: initialPageData.get('is_feed', true),
                is_deid: initialPageData.get('is_deid', true),
                model_type: initialPageData.get('model_type', true),
            },
        }));
        $('#createExportOptionsModal').on('show.bs.modal', function () {
            hqImport('analytix/js/kissmetrix').track.event("Clicked New Export");
        });

        $("#export-list").koApplyBindings(exportListModel({
            exports: initialPageData.get("exports"),
        }));
    });
});
