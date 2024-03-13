hqDefine("hqwebapp/js/bootstrap3/widgets",[
    'jquery',
    'underscore',
    '@mapbox/mapbox-gl-geocoder/dist/mapbox-gl-geocoder.min',
    'hqwebapp/js/initial_page_data',
    'select2/dist/js/select2.full.min',
    'jquery-ui/ui/widgets/datepicker',
], function ($, _, MapboxGeocoder, initialPageData) {
    var init = function () {
        var MAPBOX_ACCESS_TOKEN = initialPageData.get(
            "mapbox_access_token"
        );
        // .hqwebapp-select2 is a basic select2-based dropdown or multiselect
        _.each($(".hqwebapp-select2"), function (element) {
            $(element).select2({
                width: '100%',
            });
            if (window.USE_BOOTSTRAP5 && $(element).hasClass('is-invalid')) {
                $(element).data('select2').$container.addClass('is-invalid');
            }
            if (window.USE_BOOTSTRAP5 && $(element).hasClass('is-valid')) {
                $(element).data('select2').$container.addClass('is-valid');
            }
        });

        // .hqwebapp-autocomplete also allows for free text entry
        _.each($(".hqwebapp-autocomplete"), function (input) {
            var $input = $(input);
            $input.select2({
                multiple: true,
                tags: true,
                width: '100%',
            });
        });

        _.each($(".hqwebapp-autocomplete-email"), function (input) {
            var $input = $(input);
            $input.select2({
                multiple: true,
                placeholder: ' ',
                tags: true,
                tokenSeparators: [','],
                width: '100%',
                createTag: function (params) {
                    // Support pasting in comma-separated values
                    var terms = parseEmails(params.term);
                    if (terms.length === 1) {
                        return {
                            id: terms[0],
                            text: terms[0],
                        };
                    }
                    $input.select2('close');
                    var values = $input.val() || [];
                    if (!_.isArray(values)) {
                        values = [values];
                    }
                    _.each(terms, function (term) {
                        if (!_.contains(values, term)) {
                            $input.append(new Option(term, term));
                            values.push(term);
                        }
                    });
                    $input.val(values).trigger("change");

                    return null;
                },
            });
        });

        _.each($(".geocoder-proximity"), function (input) {
            var $input = $(input).find('input');

            function getGeocoderItem(item) {
                var inputEl = $input;
                var geoObj = {};
                geoObj.place_name = item.place_name;
                geoObj.coordinates = {
                    longitude: item.geometry.coordinates[0],
                    latitude: item.geometry.coordinates[1],
                };
                geoObj.bbox = item.bbox;
                inputEl.attr("value", JSON.stringify(geoObj));
                return item.place_name;
            }

            function getGeocoderValue() {
                var geocoderValue = $input.val();
                if (geocoderValue) {
                    geocoderValue = JSON.parse(geocoderValue);
                    return geocoderValue.place_name;
                }
                return null;
            }

            var geocoder = new MapboxGeocoder({
                accessToken: MAPBOX_ACCESS_TOKEN,
                types:
                    "country,region,place,postcode,locality,neighborhood",
                getItemValue: getGeocoderItem,
            });

            geocoder.addTo(".geocoder-proximity");
            var geocoderValue = getGeocoderValue();
            if (geocoderValue) {
                geocoder.setInput(getGeocoderValue());
            }
        });

        _.each($(".date-picker"), function (input) {
            $(input).datepicker({ dateFormat: "yy-mm-dd" });
        });
    };

    var parseEmails = function (input) {
        return $.trim(input).split(/[, ]\s*/);
    };

    $(function () {
        init();
    });

    return {
        init: init,
        parseEmails: parseEmails, // export for testing
    };
});
