import $ from 'jquery';
import ko from 'knockout';

$(function () {
    $("#js-ko-model-dynamic").koApplyBindings(function () {
        return {
            letters: ['eins', 'zwei', 'drei'],
            value: ko.observable('eins'),
        };
    });
});
