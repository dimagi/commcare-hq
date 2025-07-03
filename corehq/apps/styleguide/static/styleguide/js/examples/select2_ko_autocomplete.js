import $ from 'jquery';
import ko from 'knockout';

$(function () {
    $("#js-ko-model-autocomplete").koApplyBindings(function () {
        return {
            dishes: [
                'Gorgonzola salad with star anise dressing',
                'Swede and kohlrabi soup',
                'Gorgonzola and marjoram risotto',
                'Tuna tart with gorgonzola sauce',
                'Potato salad with bergamot dressing',
                'Marrow salad with orange dressing',
                'Orange and plumcot cake',
                'Orange and strawberry muffins',
            ],
            value: ko.observable(''),
        };
    });
});
