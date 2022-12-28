hqDefine("cloudcare/js/form_entry/spec/main", [
    "hqwebapp/js/mocha",
], function (
    hqMocha
) {
    hqRequire([
        "cloudcare/js/form_entry/spec/utils_spec",
    ], function () {
        hqMocha.run();
    });

    return 1;
});
