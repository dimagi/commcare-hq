/*global MapboxGeocoder*/
hqDefine("cloudcare/js/form_entry/utils", function () {
    var module = {
        resourceMap: undefined,
    };

    module.touchformsError = function (message) {
        return hqImport("cloudcare/js/form_entry/errors").GENERIC_ERROR + message;
    };

    module.isWebApps = function () {
        var FormplayerFrontend = hqImport("cloudcare/js/formplayer/app"),
            environment = FormplayerFrontend.getChannel().request('currentUser').environment;
        return environment === hqImport("cloudcare/js/formplayer/constants").WEB_APPS_ENVIRONMENT;
    };

    module.reloginErrorHtml = function () {
        if (module.isWebApps()) {
            var url = hqImport("hqwebapp/js/initial_page_data").reverse('login_new_window');
            return _.template(gettext("Looks like you got logged out because of inactivity, but your work is safe. " +
                                      "<a href='<%- url %>' target='_blank'>Click here to log back in.</a>"))({url: url});
        } else {
            // target=_blank doesn't work properly within an iframe
            return gettext("You have been logged out because of inactivity.");
        }
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
        var form = hqImport("cloudcare/js/form_entry/form_ui").Form(formJSON),  // circular dependency
            $debug = $('#cloudcare-debugger'),
            CloudCareDebugger = hqImport('cloudcare/js/debugger/debugger').CloudCareDebuggerFormEntry,
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

        return form;
    };

    /**
     * Sets a div to be a mapbox geocoder input
     * @param {(string|string[])} divId - Div ID for the Mapbox input
     * @param {Object} itemCallback - function to call back after new search
     * @param {Object} clearCallBack - function to call back after clearing the input
     * @param {Object} initialPageData - initial_page_data object
     */
    module.renderMapboxInput = function (divId, itemCallback, clearCallBack, initialPageData) {
        var defaultGeocoderLocation = initialPageData.get('default_geocoder_location') || {};
        var geocoder = new MapboxGeocoder({
            accessToken: initialPageData.get("mapbox_access_token"),
            types: 'address',
            enableEventLogging: false,
            getItemValue: itemCallback,
        });
        if (defaultGeocoderLocation.coordinates) {
            geocoder.setProximity(defaultGeocoderLocation.coordinates);
        }
        geocoder.on('clear', clearCallBack);
        geocoder.addTo('#' + divId);
        // Must add the form-control class to the input created by mapbox in order to edit.
        var inputEl = $('input.mapboxgl-ctrl-geocoder--input');
        inputEl.addClass('form-control');
        inputEl.on('keydown', _.debounce(self._inputOnKeyDown, 200));
    };

    /**
     * Composes a boardcast object from mapbox result to be used by receivers
     * @param {Object} mapboxResult - Mapbox query result object
     */
    module.getBroadcastObject = function (mapboxResult) {
        var broadcastObj = {
            full: mapboxResult.place_name,
        };
        mapboxResult.context.forEach(function (contextValue) {
            try {
                if (contextValue.id.startsWith('postcode')) {
                    broadcastObj.zipcode = contextValue.text;
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

    return module;
});
