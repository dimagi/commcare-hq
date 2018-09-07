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
        $(".locations-widget-autocomplete").each(function () {
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

        $(".locations-widget-primary").each(function () {
            var $select = $(this),
                $source = $('#' + $select.data("sourceCssId")),
                value = $select.val();

            // This custom event is fired in autocomplete_select_widget.html
            $source.on('select-ready', function () {
                updateSelect2($source, $select);
                // set initial value
                $select.select2("val", value);
            });

            // Change options/value for css_id based on what's chosen for source_css_id
            $source.on('change', function () {
                updateSelect2($source, $select);
                if (!$(this).select2('data').length) {
                    // if no options available, set to null
                    $select.val(null);
                } else {
                    var currentValue = $select.val();
                    var availableValues = _.map($source.select2('data'), function (item) { return item.id; });
                    // set as first value of option
                    if (!currentValue || !availableValues.includes(currentValue)) {
                        $select.select2("val", $source.select2('data')[0].id);
                    }

                }
            }).trigger('change');
        });
    });
});
