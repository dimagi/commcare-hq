import hqMocha from "mocha/js/main";
import "commcarehq";

import "cloudcare/js/form_entry/spec/entries_spec";
import "cloudcare/js/form_entry/spec/form_ui_spec";
import "cloudcare/js/form_entry/spec/integration_spec";
import "cloudcare/js/form_entry/spec/utils_spec";
import "cloudcare/js/form_entry/spec/web_form_session_spec";

hqMocha.run();
