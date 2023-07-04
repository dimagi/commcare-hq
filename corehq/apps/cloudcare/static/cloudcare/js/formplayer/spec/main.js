hqDefine("cloudcare/js/formplayer/spec/main", [
    "hqwebapp/js/mocha",
], function (
    hqMocha
) {
    hqRequire([
        "cloudcare/js/formplayer/spec/hq_events_spec",
    ], function () {
        hqMocha.run();
    });

    return 1;
});
