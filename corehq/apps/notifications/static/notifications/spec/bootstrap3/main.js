import hqMocha from "mocha/js/main";
import "commcarehq";

import "notifications/spec/bootstrap3/service_spec";

$(function () {
    hqMocha.run();
});
