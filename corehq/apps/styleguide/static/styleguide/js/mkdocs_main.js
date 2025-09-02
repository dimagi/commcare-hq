import 'commcarehq';

import $ from 'jquery';
import 'styleguide/js/main';

// TODO: Determine base url fromm settings
function setPrefilter() {
    $.ajaxPrefilter(function (options, originalOptions, jqXHR) {
      // If the URL is relative, rewrite it to your Django server
      if (options.url.startsWith("/")) {
          options.url = "http://localhost:8000" + options.url;
      }
    });
 }

$(function () {
    setPrefilter();
    console.log("Loaded mkdocs_main.js and set ajax prefilter")
});
