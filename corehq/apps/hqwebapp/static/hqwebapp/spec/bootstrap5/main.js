import hqMocha from "mocha/js/main";

import "hqwebapp/spec/assert_properties_spec";
import "hqwebapp/spec/email_validator_spec";
import "hqwebapp/spec/bootstrap5/inactivity_spec";
import "hqwebapp/spec/urllib_spec";
import "hqwebapp/spec/bootstrap5/widgets_spec";

hqMocha.run();
