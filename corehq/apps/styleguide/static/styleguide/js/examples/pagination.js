import $ from 'jquery';
import ko from 'knockout';
import _ from 'underscore';
import 'hqwebapp/js/components/pagination';

$(function () {
    let paginationExample = function () {
        let self = {};

        self.items = ko.observableArray();
        self.perPage = ko.observable();

        // Most of the time the widget will only deal with a page of items at a time
        // and goToPage will be an ajax call that will fetch some items and possibly a totalItems value
        self.allItems = _.map(_.range(23), function (i) { return "Item #" + (i + 1); });
        self.totalItems = ko.observable(self.allItems.length);
        self.goToPage = function (page) {
            self.items(self.allItems.slice(self.perPage() * (page - 1), self.perPage() * page));
        };

        // Initialize with first page of data
        self.onPaginationLoad = function () {
            self.goToPage(1);
        };

        return self;
    };

    $("#js-pagination-example").koApplyBindings(paginationExample());
});
