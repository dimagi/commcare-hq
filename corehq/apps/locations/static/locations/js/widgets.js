'use strict';
hqDefine("locations/js/widgets", [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'underscore',
    'hqwebapp/js/toggles',
    'select2/dist/js/select2.full.min',
], function (
    $,
    initialPageData,
    _,
    toggles
) {
    // Update the options available to one select2 to be
    // the selected values from another (multiselect) select2
    function updateSelect2($source, $select) {
        $select.find("option").remove();
        _.each($source.select2('data'), function (result) {
            const fullLengthName = result.text || result.name;
            let $option;
            if (toggles.toggleEnabled('LOCATION_FIELD_USER_PROVISIONING')) {
                const truncatedName = truncateLocationName(fullLengthName, $select);
                $option = new Option(truncatedName, result.id);
            } else {
                $option = new Option(fullLengthName, result.id);
            }
            $option.setAttribute('title', result.title);
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
                    if (toggles.toggleEnabled('LOCATION_FIELD_USER_PROVISIONING')) {
                        let selectedLocations = Array.from($select[0].selectedOptions);
                        if (selectedLocations.length > 0) {
                            let locIds = selectedLocations.map(option => option.value);
                            data.results.forEach(result => {
                                if (locIds.includes(result.id)) {
                                    result.disabled = true;
                                }
                            });
                        }
                    }
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
                if (toggles.toggleEnabled('LOCATION_FIELD_USER_PROVISIONING')) {
                    const truncatedName = truncateLocationName(fullLengthName, $select);
                    return truncatedName;
                } else {
                    return fullLengthName;
                }
            },
        });

        var initial = options.initial;
        if (initial) {
            if (!_.isArray(initial)) {
                initial = [initial];
            }
            _.each(initial, function (result) {
                var $option = new Option(result.text, result.id);
                $option.setAttribute('title', result.title);
                $select.append($option);
            });
            $select.val(_.pluck(initial, 'id')).trigger('change');
        }

        $select.trigger('select-ready');
    }

    function updateScreenReaderNotification(notificationText, notificationElementId) {
        const srNotification = $(notificationElementId);
        if (notificationText) {
            srNotification.html("<p>" + notificationText + "</p>");
            srNotification.attr("aria-live","assertive");
        } else {
            srNotification.attr("aria-live","off");
        }
    }

    function handleLocationWarnings(select) {
        const editorCanAccessAllLocations = initialPageData.get("can_access_all_locations");
        const editableCanAccessAllLocations = initialPageData.get("editable_user_can_access_all_locations");
        if (editableCanAccessAllLocations && editorCanAccessAllLocations) {
            return;
        }
        const requestDomain = initialPageData.get('domain');
        const selectedLocations = select.val();
        const requestUserDomainMemberships = initialPageData.get('request_user_domain_memberships');
        const requestUserLocations = _.find(requestUserDomainMemberships, function (dm) {
            if (dm.domain === requestDomain) {
                return dm.assigned_location_ids;
            }
        });
        let shareLocations = false;
        _.every(selectedLocations, function (locationId) {
            if (_.contains(requestUserLocations, locationId)) {
                shareLocations = true;
            }
        });

        const noCommonLocationWarning = $("#no-common-location");
        const noAssignedLocationsWarning = $("#no-assigned-locations");
        if (!shareLocations) {
            updateScreenReaderNotification(noCommonLocationWarning.text(), "#sr-no-shared-location-region");
            noCommonLocationWarning.show();
        } else {
            updateScreenReaderNotification(null, "#sr-no-shared-location-region");
            noCommonLocationWarning.hide();
        }
        if (selectedLocations.length < 1) {
            updateScreenReaderNotification(noAssignedLocationsWarning.text(), "#sr-no-locations-assigned-region");
            noAssignedLocationsWarning.show();
        } else {
            updateScreenReaderNotification(null, "#sr-no-locations-assigned-region");
            noAssignedLocationsWarning.hide();
        }
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
                $option.setAttribute('title', value.title);
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
                handleLocationWarnings($source);
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
