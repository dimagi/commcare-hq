import 'commcarehq';

import initialPageData from 'hqwebapp/js/initial_page_data';

import { sayHello } from "prototype/js/webpack_utils/shared_tooling";
sayHello();

console.log('another webpack test\n');
console.log("below is a test of initial page data:");
console.log(initialPageData.get("test_initial"));
