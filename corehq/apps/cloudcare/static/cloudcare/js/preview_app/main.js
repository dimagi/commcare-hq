hqDefine("cloudcare/js/preview_app/main",[
    "hqwebapp/js/initial_page_data",
], function (initial_page_data) {
    $(function () {
        var MAPBOX_ACCESS_TOKEN = initial_page_data.get('mapbox_access_token'); // maps api is loaded on-demand
        console.log('main.js previewapp',MAPBOX_ACCESS_TOKEN)
        var geolocation = initial_page_data.get('default_geocoder_location');
        console.log(geolocation)
        hqImport('cloudcare/js/preview_app/preview_app').start({
            apps: [initial_page_data.get('app')],
            language: initial_page_data.get('language'),
            username: initial_page_data.get('username'),
            domain: initial_page_data.get('domain'),
            formplayer_url: initial_page_data.get('formplayer_url'),
            singleAppMode: true,
            phoneMode: true,
            oneQuestionPerScreen: !initial_page_data.get('is_dimagi'),
            allowedHost: initial_page_data.get('allowed_host'),
            environment: initial_page_data.get('environment'),
            debuggerEnabled: initial_page_data.get('debugger_enabled'),
        });

        hqImport("cloudcare/js/util").injectMarkdownAnchorTransforms();

        $('.dragscroll').on('scroll', function () {
            $('.form-control').blur();
        });

        // Adjust for those pesky scrollbars
        _.each($('.scrollable-container'), function (sc) {
            var scrollWidth = $(sc).prop('offsetWidth') - $(sc).prop('clientWidth');
            $(sc).addClass('has-scrollbar-' + scrollWidth);
        });
    });
});
