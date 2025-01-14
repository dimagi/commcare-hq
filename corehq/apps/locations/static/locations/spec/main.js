console.log("i am in locations/spec/main");

import hqMocha from "mocha/js/main";
import "commcarehq";

import "locations/spec/types_spec";
import "locations/spec/location_drilldown_spec";

hqMocha.run();
