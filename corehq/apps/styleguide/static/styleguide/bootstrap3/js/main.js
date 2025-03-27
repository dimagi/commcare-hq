import "commcarehq";
import $ from "jquery";

// Molecules page
import "hqwebapp/js/components/select_toggle";
import "styleguide/bootstrap3/js/feedback";
import "styleguide/bootstrap3/js/inline_edit";
import "styleguide/bootstrap3/js/multiselect";
import "styleguide/bootstrap3/js/pagination";
import "styleguide/bootstrap3/js/search_box";
import "styleguide/bootstrap3/js/select2";

// Organisms page
$(function () {
  $('.styleguide-example form').submit(function (e) {
    e.preventDefault();
  });
});
