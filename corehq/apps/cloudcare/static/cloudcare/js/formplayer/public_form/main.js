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
    };

    // land straight in the target form by reusing the get_endpoint deep link.
    // Set before start() so it routes there rather than to the app list, and
    // with replaceState so the respondent's Back does not leave the form
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
