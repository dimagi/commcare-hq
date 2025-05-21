import $ from 'jquery';
import ko from 'knockout';
import "select2/dist/js/select2.full.min";
import "hqwebapp/js/select2_knockout_bindings.ko";
import "hqwebapp/js/bootstrap3/widgets";

$(function () {
    $("#example-select2 .basic").select2();

    if ($("#example-select2").length) {
        $("#example-select2 .ko-model-dynamic").koApplyBindings(function () {
            return {
                letters: ['eins', 'zwei', 'drei'],
                value: ko.observable('eins'),
            };
        });

        $("#example-select2 .ko-model-static").koApplyBindings();
    }
});
