/* globals ko */
$(function () {
    "use strict";
    if ($("#bulk_upload_form").get(0)) {
        ko.applyBindings(
            {
                file: ko.observable(null)
            },
            $("#bulk_upload_form").get(0)
        );
    }

    // modify download url to pass extra option
    function ConsumptionOptionsViewModel(base_url) {
        this.base_url = base_url;
        this.include_consumption = ko.observable(false);
        self = this;
        this.url = ko.computed(function() {
            // ternary prevents adding include_consumption=false to other
            // bulk pages
            return self.base_url + (self.include_consumption() ? "?include_consumption=true" : "")
        });
    }

    ko.applyBindings(
        new ConsumptionOptionsViewModel($("#download_link").get(0).href),
        $("#download_block").get(0)
    );
});
