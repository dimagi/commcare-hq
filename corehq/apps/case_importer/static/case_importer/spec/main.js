import hqMocha from "mocha/js/main";
import "commcarehq";

import "case_importer/spec/excel_fields_spec";

$(function () {
    hqMocha.run();
});
