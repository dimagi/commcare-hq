'use strict';
hqDefine("cloudcare/js/formplayer/spec/main", [
    "mocha/js/main",
], function (
    hqMocha
) {
    hqRequire([
        "cloudcare/js/formplayer/spec/hq_events_spec",
        "cloudcare/js/formplayer/spec/menu_list_spec",
        "cloudcare/js/formplayer/spec/session_middleware_spec",
    ], function () {
        hqMocha.run();
    });

    return 1;
});
