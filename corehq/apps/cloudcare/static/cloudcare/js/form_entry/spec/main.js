'use strict';
hqDefine("cloudcare/js/form_entry/spec/main", [
    "mocha/js/main",
], function (
    hqMocha
) {
    hqRequire([
        "cloudcare/js/form_entry/spec/case_list_pagination_spec",
        "cloudcare/js/form_entry/spec/entries_spec",
        "cloudcare/js/form_entry/spec/form_ui_spec",
        "cloudcare/js/form_entry/spec/integration_spec",
        "cloudcare/js/form_entry/spec/utils_spec",
        "cloudcare/js/form_entry/spec/web_form_session_spec",
    ], function () {
        hqMocha.run();
    });

    return 1;
});
