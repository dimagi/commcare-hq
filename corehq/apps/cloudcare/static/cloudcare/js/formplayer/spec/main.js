hqDefine("cloudcare/js/formplayer/spec/main", [
    "hqwebapp/js/mocha",
], function (
    hqMocha
) {
    hqRequire([
        "cloudcare/js/formplayer/spec/hq_events_spec",
        "cloudcare/js/formplayer/spec/menu_list_spec",
        "cloudcare/js/formplayer/spec/session_middleware_spec",
        "cloudcare/js/formplayer/spec/user_spec",
        "cloudcare/js/formplayer/spec/utils_spec",
    ], function () {
        hqMocha.run();
    });

    return 1;
});
