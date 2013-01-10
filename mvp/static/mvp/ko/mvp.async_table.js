var CHWIndicatorTable = function (options) {
    'use strict';
    var self = this;

    self.categories = ko.observableArray(ko.utils.arrayMap(options.categories, function (category) {
        return new MVISCategory(category);
    }));

    self.init = function () {

    };

};
