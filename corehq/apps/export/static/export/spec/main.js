import hqMocha from "mocha/js/main";
import "commcarehq";

import "export/js/const";
import "export/js/utils";
import "export/js/models";

import "export/spec/data/export_instances";
import "export/spec/ExportInstance.spec";
import "export/spec/ExportColumn.spec";
import "export/spec/Exports.Utils.spec";

$(function () {
    hqMocha.run();
});
