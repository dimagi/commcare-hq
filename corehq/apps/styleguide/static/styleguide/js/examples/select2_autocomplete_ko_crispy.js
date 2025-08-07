import $ from 'jquery';
import ko from 'knockout';

$(function () {
    $("#ko-veggie-suggestions").koApplyBindings(function () {
        return {
            veggies: [
                "kale", "broccoli", "radish", "bell pepper", "sweet potato", "spinach", "cabbage",
            ],
            value: ko.observable(''),
        };
    });
});
