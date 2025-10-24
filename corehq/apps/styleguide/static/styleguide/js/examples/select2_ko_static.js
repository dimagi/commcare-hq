import $ from 'jquery';

$(function () {
    const $el = $("#js-ko-model-static");
    if ($el.length) {
        $el.koApplyBindings();
    }
});
