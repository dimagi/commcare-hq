import $ from 'jquery';
import multiselect_utils from "hqwebapp/js/multiselect_utils";

let listener = function() {
  console.log("Triggered willSelectAllListener");
};

$(function () {
  multiselect_utils.createFullMultiselectWidget('example-multiselect', {
    selectableHeaderTitle: gettext("Available Letters"),
    selectedHeaderTitle: gettext("Letters Selected"),
    searchItemTitle: gettext("Search Letters..."),
    disableModifyAllActions: false,
    willSelectAllListener: listener,
  });
});
