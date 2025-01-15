import hqMocha from "mocha/js/main";
import "commcarehq";

import "export/spec/ExportInstance.spec";
import "export/spec/ExportColumn.spec";
import "export/spec/Exports.Utils.spec";

hqMocha.run();
