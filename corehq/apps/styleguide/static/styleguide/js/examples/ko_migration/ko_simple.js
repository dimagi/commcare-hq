import $ from 'jquery';
import ko from 'knockout';
import initialPageData from 'hqwebapp/js/initial_page_data';

$(function () {
    var simpleModel = function () {
        let self = {};
        self.name = ko.observable(initialPageData.get("ko_simple_name"));
        self.count = ko.observable(0);
        self.isVisible = ko.observable(false);
        self.greeting = ko.computed(function () {
            return 'Hello, ' + self.name() + '!';
        });
        self.incrementCount = function () {
            self.count(self.count() + 1);
        };
        self.toggleVisibility = function () {
            self.isVisible(!self.isVisible());
        };
        return self;
    };
    $("#simple-ko-start-example").koApplyBindings(simpleModel());
});
