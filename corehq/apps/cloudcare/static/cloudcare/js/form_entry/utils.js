'use strict';
hqDefine("cloudcare/js/form_entry/utils", [
    'jquery',
    'knockout',
    'underscore',
    '@mapbox/mapbox-gl-geocoder/dist/mapbox-gl-geocoder.min',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/toggles',
    'cloudcare/js/form_entry/const',
    'cloudcare/js/form_entry/errors',
    'cloudcare/js/formplayer/constants',
], function (
    $,
    ko,
    _,
    MapboxGeocoder,
    initialPageData,
    toggles,
    formEntryConst,
    errors
) {
    var module = {
        resourceMap: undefined,
    };

    module.touchformsError = function (message) {
        return errors.GENERIC_ERROR + message;
    };

    module.jsError = function (message) {
        return errors.JS_ERROR + message;
    };

    /**
     * Compares the equality of two answer sets.
     * @param {(string|string[])} answer1 - A string of answers or a single answer
     * @param {(string|string[])} answer2 - A string of answers or a single answer
     */
    module.answersEqual = function (answer1, answer2) {
        if (answer1 instanceof Array && answer2 instanceof Array) {
            return _.isEqual(answer1, answer2);
        } else if (answer1 === answer2) {
            return true;
        }
        return false;
    };

    /**
     * Initializes a new form to be used by the formplayer.
     * @param {Object} formJSON - The json representation of the form
     * @param {Object} resourceMap - Function for resolving multimedia paths
     * @param {Object} $div - The jquery element that the form will be rendered in.
     */
    module.initialRender = function (formJSON, resourceMap, $div) {
        var defer = $.Deferred();
        hqRequire([
            "cloudcare/js/debugger/debugger",
            "cloudcare/js/form_entry/form_ui",
        ], function (Debugger, FormUI) {
            var form = FormUI.Form(formJSON),
                $debug = $('#cloudcare-debugger'),
                CloudCareDebugger = Debugger.CloudCareDebuggerFormEntry,
                cloudCareDebugger;
            module.resourceMap = resourceMap;
            ko.cleanNode($div[0]);
            $div.koApplyBindings(form);

            if ($debug.length) {
                cloudCareDebugger = new CloudCareDebugger({
                    baseUrl: formJSON.xform_url,
                    formSessionId: formJSON.session_id,
                    username: formJSON.username,
                    restoreAs: formJSON.restoreAs,
                    domain: formJSON.domain,
                });
                ko.cleanNode($debug[0]);
                $debug.koApplyBindings(cloudCareDebugger);
            }

            defer.resolve(form);
        });
        return defer.promise();
    };

    /**
     * Sets a div to be a mapbox geocoder input
     * @param {(string|string[])} divId - Div ID for the Mapbox input
     * @param {function} itemCallback - function to call back after new search
     * @param {function} clearCallBack - function to call back after clearing the input
     * @param {function|undefined} inputOnKeyDown - inputOnKeyDown function (optional)
     * @param {boolean} showGeolocationButton - show geolocation button. Defaults to false. (optional)
     * @param {boolean} geolocateOnLoad - geolocate the user's location on load. Defaults to false. (optional)
     * @param {boolean} useBoundingBox - use default locations bbox to filter results. Defaults to false. (optional)
     * @param {string} responseDataTypes - set Mapbox's data type response https://docs.mapbox.com/api/search/geocoding/#data-types (optional)
    */
    module.renderMapboxInput = function ({
        divId,
        itemCallback,
        clearCallBack,
        inputOnKeyDown,
        showGeolocationButton = false,
        geolocateOnLoad = false,
        useBoundingBox = false,
        responseDataTypes = 'address',
    }) {
        showGeolocationButton = showGeolocationButton || toggles.toggleEnabled('GEOCODER_MY_LOCATION_BUTTON');
        geolocateOnLoad = geolocateOnLoad || toggles.toggleEnabled('GEOCODER_AUTOLOAD_USER_LOCATION');
        var setProximity = toggles.toggleEnabled('GEOCODER_USER_PROXIMITY');
        var defaultGeocoderLocation = initialPageData.get('default_geocoder_location') || {};
        var geocoder = new MapboxGeocoder({
            accessToken: initialPageData.get("mapbox_access_token"),
            types: responseDataTypes,
            enableEventLogging: false,
            enableGeolocation: showGeolocationButton,
        });
        if (setProximity && geocoder.geolocation.isSupport()) {
            geocoder.geolocation.getCurrentPosition().then(function (position) {
                geocoder.setProximity(position.coords);
            }).catch(error => console.log("Unable to set geocoder proximity: ", error.message));
        } else if (defaultGeocoderLocation.coordinates) {
            geocoder.setProximity(defaultGeocoderLocation.coordinates);
        }
        if (setProximity && useBoundingBox && defaultGeocoderLocation.bbox) {
            geocoder.setBbox(defaultGeocoderLocation.bbox);
        }
        geocoder.on('clear', clearCallBack);
        geocoder.on('result', (item) => itemCallback(item.result));
        geocoder.addTo('#' + divId);
        const divEl = $("#" + divId);
        const liveRegionEl = $("#" + divId + "-sr[role='region']");
        // Must add the form-control class to the input created by mapbox in order to edit.
        var inputEl = divEl.find('input.mapboxgl-ctrl-geocoder--input');
        inputEl.addClass('form-control');
        inputEl.on('keydown', _.debounce((e) => {
            if (inputOnKeyDown) {
                inputOnKeyDown(e);
            }

            // This captures arrow up/down events on geocoder input box and updates the
            // screen reader live region with the current highlighted value.
            if (e.key === "ArrowUp" || e.key === "ArrowDown") {
                const currentOption = divEl.find("ul.suggestions li.active").text();
                liveRegionEl.html("<p>" + currentOption + "</p>");
            }
        }, 200));

        // This populates the "region" html node with the first option, so that it is read by
        // screen readers on focus.
        geocoder.on('results', (items) => {
            if (items && !_.isEmpty(items.features)) {
                liveRegionEl.html("<p>" + items.features[0].place_name + "</p>");
            }
        });

        if (geolocateOnLoad) {
            geocoder._geolocateUser();
        }
    };

    /**
     * Composes a broadcast object from mapbox result to be used by receivers
     * @param {Object} mapboxResult - Mapbox query result object
     */
    module.getAddressBroadcastObject = function (mapboxResult) {
        var broadcastObj = {
            full: mapboxResult.place_name,
            geopoint: mapboxResult.geometry.coordinates[1] + ' ' + mapboxResult.geometry.coordinates[0],
        };
        mapboxResult.context.forEach(function (contextValue) {
            try {
                if (contextValue.id.startsWith('district')) {
                    broadcastObj.county = contextValue.text;
                    broadcastObj.district = contextValue.text;
                } else if (contextValue.id.startsWith('postcode')) {
                    broadcastObj.zipcode = contextValue.text;
                    broadcastObj.postcode = contextValue.text;
                } else if (contextValue.id.startsWith('place')) {
                    broadcastObj.city = contextValue.text;
                } else if (contextValue.id.startsWith('country')) {
                    broadcastObj.country = contextValue.text;
                    if (contextValue.short_code) {
                        broadcastObj.country_short = contextValue.short_code;
                    }
                } else if (contextValue.id.startsWith('region')) {
                    broadcastObj.region = contextValue.text;
                    // TODO: Deprecate state_short and state_long.
                    broadcastObj.state_long = contextValue.text;
                    if (contextValue.short_code) {
                        broadcastObj.state_short = contextValue.short_code.replace('US-', '');
                    }
                    // If US region, it's actually a state so add us_state.
                    if (contextValue.short_code && contextValue.short_code.startsWith('US-')) {
                        broadcastObj.us_state = contextValue.text;
                        broadcastObj.us_state_short = contextValue.short_code.replace('US-', '');
                    }
                }
            } catch (err) {
                // Swallow error, broadcast best effort. Consider logging.
            }
        });
        // street composed of (optional) number and street name.
        if (mapboxResult.address && mapboxResult.text) {
            broadcastObj.street = mapboxResult.address + ' ' + mapboxResult.text;
        } else {
            broadcastObj.street = mapboxResult.address || mapboxResult.text;
        }
        return broadcastObj;
    };

    var getRoot = (question, stopCallback) => {
        if (question.parent === undefined) {
            return undefined;
        }

        // logic in case the question is in a group or repeat or nested group, etc.
        let curr = question.parent;
        while (curr.parent && !stopCallback(curr)) {
            curr = curr.parent;
        }
        return curr;
    };

    /**
     * Gets a question's form, which will be the root of the question's tree.
    **/
    module.getRootForm = (question) => {
        return getRoot(question, function () {
            // Don't stop for any reason, just return topmost container
            return false;
        });
    };

    /**
     * Get the appropriate Container to which a question can broadcast messages.
     * This is typically the root form, but for questions inside of repeats, it's
     * the current group (a child of the repeat juncture).
    **/
    module.getBroadcastContainer = (question) => {
        return getRoot(question, function (container) {
            // Return first containing repeat group, or form if there are no ancestor repeats
            var parent = container.parent.parent;
            return parent && parent.type && parent.type() === formEntryConst.REPEAT_TYPE;
        });
    };

    return module;
});
