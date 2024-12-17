hqDefine('locations/js/import', [
    'jquery',
    'knockout',
    'analytix/js/google',
    'commcarehq',
], function (
    $,
    ko,
    googleAnalytics
) {
    $(function () {
        googleAnalytics.track.click($('#download_link'), 'Organization Structure', 'Bulk Import', 'Download');
        $("button[type='submit']").click(function () {
            googleAnalytics.track.event('Organization Structure', 'Bulk Import', 'Upload');
        });

        if ($("#bulk_upload_form").get(0)) {
            $("#bulk_upload_form").koApplyBindings({
                file: ko.observable(null),
            });
        }

        // modify download url to pass extra options
        function consumptionOptionsViewModel(baseUrl) {
            var self = {};
            self.base_url = baseUrl;
            self.include_consumption = ko.observable(false);
            self.url = ko.computed(function () {
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
