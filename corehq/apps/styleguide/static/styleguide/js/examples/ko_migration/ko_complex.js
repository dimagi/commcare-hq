import $ from 'jquery';
import ko from 'knockout';
import initialPageData from 'hqwebapp/js/initial_page_data';

$(function () {
    var kvModel = function (key, value) {
        let self = {};
        self.key = ko.observable(key);
        self.value = ko.observable(value);
        return self;
    };
    var complexModel = function (initialData) {
        let self = {};
        self.keyValuePairs = ko.observableArray(initialData.map(function(item) {
            return kvModel(item.key, item.value);
        }));
        self.addKeyValuePair = function () {
            self.keyValuePairs.push(kvModel('', ''));
        };
        self.removeKeyValuePair = function (pair) {
            self.keyValuePairs.remove(pair);
        };
        return self;
    };
    $("#complex-ko-start-example").koApplyBindings(complexModel(initialPageData.get("complex_initial_value")));
});
