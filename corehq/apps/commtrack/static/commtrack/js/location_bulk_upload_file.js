/* globals ko */
$(function () {
    "use strict";
    if ($("#bulk_upload_form").get(0)) {
        $("#bulk_upload_form").koApplyBindings({
            file: ko.observable(null),
        });
    }

    // modify download url to pass extra options
    function ConsumptionOptionsViewModel(base_url) {
        this.base_url = base_url;
        this.include_consumption = ko.observable(false);
        self = this;
        this.url = ko.computed(function() {
            return (
                self.base_url + "?"
                + (self.include_consumption() ? "include_consumption=true" : "")
                + ((self.include_consumption() && self.include_ids()) ? "&" : "")
            );
        });
    }

    $("#download_block").koApplyBindings(
        new ConsumptionOptionsViewModel($("#download_link").get(0).href)
    );
});
