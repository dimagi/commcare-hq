import "commcarehq";
import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import FormplayerFrontend from "cloudcare/js/formplayer/app";
import Utils from "cloudcare/js/formplayer/utils/utils";
import sentry from "cloudcare/js/sentry";

$(function () {
    sentry.initSentry();

    $.ajaxSetup({
        headers: {"CommCare-Public-Session": "true"},
    });

    window.MAPBOX_ACCESS_TOKEN = initialPageData.get('mapbox_access_token');
    const options = {
        apps: initialPageData.get('apps'),
        language: initialPageData.get('language'),
        username: initialPageData.get('username'),
        domain: initialPageData.get('domain'),
        formplayer_url: initialPageData.get('formplayer_url'),
        environment: initialPageData.get('environment'),
        singleAppMode: false,
        publicFormMode: true,
        debuggerEnabled: false,
    };

    // Build a url using endpoint_id to navigate straight into the target form.
    // Set before start() so it routes there first, and with replaceState so
    // the browser's Back would not leave the form.
    const url = new Utils.CloudcareUrl({
        appId: initialPageData.get('app_build_id'),
        endpointId: initialPageData.get('endpoint_id'),
    });
    window.history.replaceState(
        null, '', '#' + Utils.objectToEncodedUrl(url.toJson()));

    FormplayerFrontend.getXSRF(options).then(function () {
        FormplayerFrontend.start(options);
    });
});
