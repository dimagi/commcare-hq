import $ from 'jquery';

$(function () {
    const $el = $("#ko-menu-generator");
    if ($el.length) {
        $el.koApplyBindings();
    }
});
