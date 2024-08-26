'use strict';
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
            var $option = new Option(truncatedName, result.id);
            $option.setAttribute('title', result.tooltip || result.title);
            $select.append($option);
        });
    }

    function truncateLocationName(name, select) {
        const nameWidthPixels = getSelectTextWidth(name, select);
        const basicInfoTabActive = $('#basic-info').hasClass('active');
        let containerWidthPixels = select.parent().width();

        // Select is hidden on locations tab. Calculate width from visible select.
        if (basicInfoTabActive) {
            const visibleSelect = $('#basic-info').find('.controls > .select')[0];
            if (!visibleSelect) {
                return name;
            }
            containerWidthPixels = $(visibleSelect).parent().width();
        // Default to select2 setting for overflow
        } else if (containerWidthPixels < 0) {
            return name;
        }
        let truncatedName;
        if (nameWidthPixels > containerWidthPixels) {
            // Conservative calc of the number of chars that will fit the container
            const averagePixelWidthPerChar = Math.ceil(nameWidthPixels / name.length);
            const maxCharCount = Math.floor(containerWidthPixels / averagePixelWidthPerChar);
            const charLengthDiff = name.length - maxCharCount;

            truncatedName = `${name.substring(0, 5)}...${name.substring(charLengthDiff + 16, name.length)}`;

            return truncatedName;
        }

        return name;
    }

    function getSelectTextWidth(text, select) {
        const fontSize = select.css('font-size');
        const fontFamily = select.css('font-family');
        const fontWeight = select.css('font-weight');
        // Create an invisible div to get accurate measure of text width
        const textDiv = $('<div id="select-text-div"></div>').text(text).css({'position': 'absolute',
            'float': 'left',
            'white-space': 'nowrap',
            'visibility': 'hidden',
            'font-size': fontSize,
            'font-weight': fontWeight,
            'font-family': fontFamily,
        });

        textDiv.appendTo('body');
        const textWidth = textDiv.width();
        textDiv.remove();

        return textWidth;
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
                var $option = new Option(result.text);
                $option.setAttribute('title', result.tooltip);
                return $option;
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
                var $option = new Option(result.text, result.id);
                $option.setAttribute('title', result.tooltip);
                $select.append($option);
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
                var $option = new Option(value.text, value.id);
                $option.setAttribute('title', value.tooltip);
                $select.append($option);
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
