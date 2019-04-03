hqDefine("locations/js/widgets_main_v3", [
    'jquery',
    'underscore',
    'select2-3.5.2-legacy/select2',
], function (
    $,
    _
) {
    // Update the options available to one select2 to be
    // the selected values from another (multiselect) select2
    function updateSelect2($source, $select) {
        var options = {
            formatResult: function (e) { return e.name; },
            formatSelection: function (e) { return e.name; },
            allowClear: true,
            placeholder: gettext("Choose a primary location"),
            formatNoMatches: function () {
                return gettext("No locations set for this user");
            },
            data: {'results': $source.select2('data')},
        };
        $select.select2(options);
    }
});
