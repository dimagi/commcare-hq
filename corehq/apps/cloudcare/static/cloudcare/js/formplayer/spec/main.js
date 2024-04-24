'use strict';
hqDefine("cloudcare/js/formplayer/spec/main", [
    "mocha/js/main",
], function (
    hqMocha
) {
    hqRequire([
        "cloudcare/js/formplayer/spec/case_list_pagination_spec",
        "cloudcare/js/formplayer/spec/debugger_spec",
        "cloudcare/js/formplayer/spec/hq_events_spec",
        "cloudcare/js/spec/markdown_spec",
        "cloudcare/js/formplayer/spec/menu_list_spec",
        "cloudcare/js/formplayer/spec/query_spec",
        "cloudcare/js/formplayer/spec/session_middleware_spec",
        "cloudcare/js/formplayer/spec/split_screen_case_search_spec",
        "cloudcare/js/formplayer/spec/user_spec",
        "cloudcare/js/formplayer/spec/utils_spec",
        "cloudcare/js/spec/utils_spec",
    ], function () {
        hqMocha.run();
    });

    return 1;
});
