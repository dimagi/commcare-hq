import "commcarehq";
import $ from "jquery";
import baseAce from "hqwebapp/js/base_ace";
import "jquery-treetable/jquery.treetable";

$(function () {
    $("#timingTable").treetable();
    var element = document.getElementById("payload");

    baseAce.initAceEditor(element, 'ace/mode/xml', {}, $("#payload").data('payload'));
});
