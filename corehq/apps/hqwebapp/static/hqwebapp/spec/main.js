hqDefine("hqwebapp/spec/main", [
    "hqwebapp/js/mocha",
], function (
    hqMocha
) {
    hqRequire([
        "hqwebapp/spec/assert_properties_spec",
        "hqwebapp/spec/inactivity_spec",
        "hqwebapp/spec/urllib_spec",
        "hqwebapp/spec/widgets_spec",
    ], function () {
        hqMocha.run();
    });

    return 1;
});
