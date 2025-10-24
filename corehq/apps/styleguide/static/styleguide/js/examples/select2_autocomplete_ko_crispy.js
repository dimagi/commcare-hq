import $ from 'jquery';
import ko from 'knockout';

$(function () {
    const $el = $("#ko-veggie-suggestions");
    if ($el.length) {
        $el.koApplyBindings(function () {
            return {
                veggies: [
                    "kale", "broccoli", "radish", "bell pepper", "sweet potato", "spinach", "cabbage",
                ],
                value: ko.observable(''),
            };
        });
    }
});
