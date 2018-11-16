/* globals FormplayerFrontend */
hqDefine("cloudcare/js/landing_page", function () {
    $(function () {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data").get;
        window.GMAPS_API_KEY = initialPageData("maps_api_key"); // maps api is loaded on-demand
        var options = {
            apps: [initialPageData("app")],
            language: initialPageData("language"),
            username: initialPageData("username"),
            domain: initialPageData("domain"),
            formplayer_url: initialPageData("formplayer_url"),
            landingPageAppMode: true,
            singleAppMode: false,
            phoneMode: false,
            oneQuestionPerScreen: false,
            allowedHost: initialPageData("allowed_host"),
            environment: initialPageData("environment"),
            debuggerEnabled: initialPageData("debugger_enabled"),
        };
        FormplayerFrontend.start(options);
    });
});
