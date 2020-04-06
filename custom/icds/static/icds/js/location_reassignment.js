hqDefine("icds/js/location_reassignment", [
    'jquery',
    'knockout',
    'hqwebapp/js/assert_properties',
    'locations/js/search',
], function (
    $,
    ko,
    assertProperties
) {
    $(function () {
        var LocationReassignmentModel = function (options) {
            assertProperties.assertRequired(options, ['baseUrl']);

            var self = {};
            self.baseUrl = options.baseUrl;

            // Download
            self.location_id = ko.observable('');
            self.url = ko.computed(function () {
                return self.baseUrl + "?location_id=" + (self.location_id() || '');
            });

            // Upload
            self.file = ko.observable();

            return self;
        };

        var $content = $("#hq-content");
        $content.koApplyBindings(LocationReassignmentModel({
            baseUrl: $content.find("#download_link").attr("href"),
        }));

        // https://stackoverflow.com/a/35489517
        // bind the form submit to the document ajax to get notified on success
        $("#bulk_upload_form").on("submit", function () {
            $.ajax({context: this});
        });

        $("#bulk_upload_form").ajaxSuccess(function (event) {
            if (event.target.id === "bulk_upload_form") {
                $(event.target).trigger('reset');
            }
        });
    });
});
