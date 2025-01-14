import hqMocha from "mocha/js/main";
import "commcarehq";

import "notifications/spec/bootstrap5/service_spec";

$(function () {
    hqMocha.run();
});
