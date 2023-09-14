hqDefine("hqmedia/js/manage_paths_main", [
    "jquery",
    "knockout",
    "hqwebapp/js/assert_properties",
    "hqwebapp/js/bootstrap3/components.ko",    // select toggle widget
], function (
    $,
    ko,
    assertProperties
) {
    var pathsModel = function (options) {
        assertProperties.assertRequired(options, ['baseUrl', 'only_missing']);
        var self = {};

        self.file = ko.observable();
        self.only_missing = ko.observable(options.only_missing);
        self.url = ko.computed(function () {
            return options.baseUrl + "?only_missing=" + self.only_missing();
        });

        return self;
    };

    $(function () {
        var $content = $("#hq-content");
        $content.koApplyBindings(pathsModel({
            baseUrl: $content.find("#download_link").attr("href"),
            only_missing: $content.find("#only_missing").val() || '',
        }));
    });
});
