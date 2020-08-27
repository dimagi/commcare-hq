
hqDefine(
    "domain/js/info_basic",
    [
        "jquery",
        "underscore",
        "@mapbox/mapbox-gl-geocoder/dist/mapbox-gl-geocoder.min",
        "hqwebapp/js/initial_page_data",
        "hqwebapp/js/select_2_ajax_widget", // for call center case owner
        "select2/dist/js/select2.full.min",
    ],
    function ($, _, MapboxGeocoder, initialPageData) {
        $(function () {
            var MAPBOX_ACCESS_TOKEN = initialPageData.get("mapbox_access_token");
            $("#id_default_timezone").select2({
                placeholder: gettext("Select a Timezone..."),
            });

            function getGeocoderItem(item) {
                var inputEl = $("#id_default_geocoder_location");
                var geoObj = {};
                geoObj.place_name = item.place_name;
                geoObj.coordinates = {'longitude': item.geometry.coordinates[0], 'latitude': item.geometry.coordinates[1]};
                inputEl.attr("value", JSON.stringify(geoObj));
                return item.place_name;
            }

            function getGeocoderValue() {
                var geocoderValue = $("#id_default_geocoder_location").val();
                if (geocoderValue) {
                    geocoderValue = JSON.parse(geocoderValue);
                    return geocoderValue.place_name;
                }
                return null;
            }

            var geocoder = new MapboxGeocoder({
                accessToken: MAPBOX_ACCESS_TOKEN,
                types: "country,region,place,postcode,locality,neighborhood",
                getItemValue: getGeocoderItem,
            });

            geocoder.addTo(".geocoder-proximity");
            var geocoderValue = getGeocoderValue();
            if (geocoderValue) {
                geocoder.setInput(getGeocoderValue());
            }

            $("#id_call_center_enabled").change(function () {
                var type = $("#id_call_center_type").closest(".control-group");
                var case_owner = $("#id_call_center_case_owner").closest(
                    ".control-group"
                );
                var case_type = $("#id_call_center_case_type").closest(
                    ".control-group"
                );
                if ($(this).is(":checked")) {
                    type.removeClass("hide");
                    case_owner.removeClass("hide");
                    case_type.removeClass("hide");
                } else {
                    type.addClass("hide");
                    case_owner.addClass("hide");
                    case_type.addClass("hide");
                }
            });
            $("#id_call_center_enabled").trigger("change");
        });
    }
);
