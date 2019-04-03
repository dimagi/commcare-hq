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

    $(function () {
        $(".locations-widget-autocomplete-v3").each(function () {
            var $select = $(this),
                options = $select.data();
            $select.select2({
                placeholder: gettext("Select a Location"),
                allowClear: true,
                multiple: options.multiselect,
                ajax: {
                    url: options.queryUrl,
                    dataType: 'json',
                    quietMillis: 500,
                    data: function (term, page) {
                        return {
                            name: term,
                            page: page,
                        };
                    },
                    results: function (data, page) {
                        // 10 results per query
                        var more = (page * 10) < data.total_count;
                        return {results: data.results, more: more};
                    },
                },
                initSelection: function (element, callback) {
                    callback(options.initialData);
                    $(element).trigger('select-ready');
                },
                formatResult: function (e) { return e.name; },
                formatSelection: function (e) { return e.name; },
            });
        });
    });
});
