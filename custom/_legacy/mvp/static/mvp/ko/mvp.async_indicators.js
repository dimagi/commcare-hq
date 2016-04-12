var MVISIndicatorTable = function (options) {
    'use strict';
    var self = this;

    self.categories = ko.observableArray(ko.utils.arrayMap(options.categories, function (category) {
        return new MVISCategory(category);
    }));

    self.init = function () {
        var _queue = new window.mvp.MVPIndicatorQueue(
            options.categories.length, function (ind, fnNext) {
                return self.categories()[ind].queueIndicators().then(fnNext);
            }
        );
        _queue.start();
    };
};

var MVISCategory = function (category_data) {
    'use strict';
    var self = this;
    self.rowspan = category_data.rowspan;
    self.category_title = category_data.category_title;
    self.category_slug = category_data.category_slug;

    self.indicators = ko.observableArray(ko.utils.arrayMap(category_data.indicators, function (indicator) {
        var indicator_obj = new MVISIndicator(indicator);
        indicator_obj.init();
        return indicator_obj;
    }));

    self.queueIndicators = function () {
        var _queue = new window.mvp.MVPIndicatorQueue(
            self.indicators().length, function (ind, fnNext) {
                return self.indicators()[ind].updateIndicator()
                    .done(fnNext)
                    .fail(fnNext);
            }
        );
        _queue.start();
        return _queue.d;
    };

    self.show_category_title = function (index) {
        index = ko.utils.unwrapObservable(index);
        return index === 0;
    };

    self.make_new_row = function (index) {
        index = ko.utils.unwrapObservable(index);
        return index !== 0;
    };

};

var MVISIndicator = function (indicator) {
    'use strict';
    var self = this;
    self.load_url = indicator.load_url;

    self.is_loaded = ko.observable(false);
    self.is_loading = ko.observable(false);
    self.show_loading = ko.computed(function () {
        return !self.is_loaded();
    });

    self.rowspan = indicator.rowspan;
    self.title = indicator.title;
    self.num_columns = indicator.table.numerators.length;
    self.loading_text = ko.observable("");

    self.default_loading_text = ko.computed(function () {
        return "Indicator " + self.loading_text();
    });
    self.num_loading_text = ko.computed(function () {
        return "Numerator " + self.loading_text();
    });
    self.denom_loading_text = ko.computed(function () {
        return "Denominator " + self.loading_text();
    });

    self.percentages = ko.observableArray(indicator.table.percentages || []);
    self.numerators = ko.observableArray(indicator.table.numerators || []);
    self.denominators = ko.observableArray(indicator.table.denominators || []);

    self.show_only_numerators = (self.rowspan === 1);

    self.init = function () {
        self.loading_text("In Queue");
    };

    self.updateIndicator = function () {
        var _updater = new window.mvp.MVPIndicatorUpdater(
            self.load_url, self.loadSuccess, self.loadError
        );
        _updater.start();
        self.is_loading(true);
        return _updater.d;
    };

    self.loadSuccess = function (data) {
        if (!data.error) {
            self.percentages(data.table.percentages || []);
            self.numerators(data.table.numerators || []);
            self.denominators(data.table.denominators || []);
            self.is_loaded(true);
            $('.mvp-table').trigger('mvp.loaded');
        } else {
            console.log("ERROR: ", data.error);
        }
    };

    self.loadError = function () {
        self.is_loading(false);
        self.loading_text("encountered errors while loading.");
    };
};

$.fn.asyncIndicators = function (options) {
    var viewModel = new MVISIndicatorTable(options);
    $(this).koApplyBindings(viewModel);
    viewModel.init();
};
