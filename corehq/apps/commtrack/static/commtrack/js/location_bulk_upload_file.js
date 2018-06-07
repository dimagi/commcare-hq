hqDefine("commtrack/js/location_bulk_upload_file", [
    'jquery',
    'knockout',
], function(
    $,
    ko
) {
    $(function () {
        "use strict";
        if ($("#bulk_upload_form").get(0)) {
            $("#bulk_upload_form").koApplyBindings({
                file: ko.observable(null),
            });
        }

        // modify download url to pass extra options
        function consumptionOptionsViewModel(base_url) {
            var self = {};
            self.base_url = base_url;
            self.include_consumption = ko.observable(false);
            self.url = ko.computed(function() {
                return (
                    self.base_url + "?"
                    + (self.include_consumption() ? "include_consumption=true" : "")
                );
            });
            return self;
        }

        $("#download_block").koApplyBindings(
            consumptionOptionsViewModel($("#download_link").get(0).href)
        );
    });
});
