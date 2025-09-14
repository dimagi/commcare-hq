import $ from 'jquery';
import ko from 'knockout';

$(function () {
    const $el = $("#js-ko-model-dynamic");
    if ($el.length) {
        $el.koApplyBindings(function () {
            return {
                letters: ['eins', 'zwei', 'drei'],
                value: ko.observable('eins'),
            };
        });
    }
});
