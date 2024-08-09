hqDefine("locations/js/widgets", [
    'jquery',
    'underscore',
    'select2/dist/js/select2.full.min',
], function (
    $,
    _
) {
    // Update the options available to one select2 to be
    // the selected values from another (multiselect) select2
    function updateSelect2($source, $select) {
        $select.find("option").remove();
        _.each($source.select2('data'), function (result) {
            const fullLengthName = result.text || result.name;
            const truncatedName = truncateLocationName(fullLengthName, $select);
            $select.append(new Option(truncatedName, result.id));
        });
    }

    function truncateLocationName(name, select) {
        const fontSize = select.css('font-size');
        const fontSizePixels = parseInt(fontSize.substring(0, fontSize.indexOf('px')));
        const containerWidthPixels = select.parent().parent().width();
        const containerWidthChars = Math.floor(containerWidthPixels / fontSizePixels);
        let truncatedName = name;
        if (name.length > containerWidthChars) {
            const charLengthDiff = name.length - containerWidthChars;
            truncatedName = `${name.substring(0, 5)}...${name.substring(charLengthDiff + 12, name.length)}`;
        }
        return truncatedName;
    }

    function initAutocomplete($select) {
        var options = $select.data();
        $select.select2({
            multiple: options.multiselect,
            allowClear: !options.multiselect,
            placeholder: options.placeholder || gettext("Select a Location"),
            width: '100%',
            ajax: {
                url: options.queryUrl,
                dataType: 'json',
                delay: 500,
                data: function (params) {
                    return {
                        q: params.term,
                        page: params.page,
                    };
                },
                processResults: function (data, params) {
                    var more = (params.page || 1) * 10 < data.total;
                    return {
                        results: data.results,
                        pagination: { more: more },
                    };
                },
            },
            templateResult: function (result) {
                return result.text || result.name;
            },
            templateSelection: function (result) {
                const fullLengthName = result.text || result.name;
                const truncatedName = truncateLocationName(fullLengthName, $select);
                return truncatedName;
            },
        });

        var initial = options.initial;
        if (initial) {
            if (!_.isArray(initial)) {
                initial = [initial];
            }
            _.each(initial, function (result) {
                $select.append(new Option(result.text, result.id));
            });
            $select.val(_.pluck(initial, 'id')).trigger('change');
        }

        $select.trigger('select-ready');
    }

    $(function () {
        $(".locations-widget-autocomplete").each(function () {
            initAutocomplete($(this));
        });

        $(".locations-widget-primary").each(function () {
            var $select = $(this),
                $source = $('#' + $select.data("sourceCssId")),
                value = $select.data("initial");

            $select.select2({
                allowClear: true,
                placeholder: gettext("Choose a primary location"),
                width: '100%',
            });

            // This custom event is fired in autocomplete_select_widget.html
            if ($source.hasClass("select2-hidden-accessible")) {
                updateSelect2($source, $select);
                $select.append(new Option(value.text, value.id));
                $select.val(value.id).trigger("change");
            } else {
                $source.on('select-ready', function () {
                    updateSelect2($source, $select);
                    $select.val(value).trigger("change");
                });
            }

            // Change options/value for css_id based on what's chosen for source_css_id
            $source.on('change', function () {
                updateSelect2($source, $select);
                var sourceOptions = $source.select2('data'),
                    newValue;
                if (!sourceOptions.length) {
                    newValue = null;
                } else {
                    newValue = $select.val();   // current value
                    if (!_.contains(_.pluck(sourceOptions, 'id'), newValue)) {
                        newValue = sourceOptions[0].id;
                    }
                }
                $select.val(newValue).trigger('change');
            });
        });
    });

    return {
        initAutocomplete: initAutocomplete,
    };
});
