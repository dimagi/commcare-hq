var MVISIndicatorTable = function (options) {
    'use strict';
    var self = this;

    self.categories = ko.observableArray(ko.utils.arrayMap(options.categories, function (category) {
        return new MVISCategory(category);
    }));

    self.init = function () {

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
    self.num_tries = 0;

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
        console.log("added to queue");
        self.loading_text("in queue.");
        queue.add(self);
    };

    self.load_success = function (data) {
        if (!data.error) {
            self.percentages(data.table.percentages || []);
            self.numerators(data.table.numerators || []);
            self.denominators(data.table.denominators || []);
            self.is_loaded(true);
        }
        queue.next(false);
    };

    self.load_error = function (error) {
        console.log("there was an error");
        console.log(error);
        // check to see if this is a real error...
        if (error.responseText && error.responseText.table) {
            self.load_success(error.responseText);
        }
        var try_again = !!(self.num_tries <= 3);
        queue.next(false);
        self.is_loading(false);
        if (try_again) {
            console.log("trying again");
            queue.add(self);
            self.loading_text("experienced a connection issue while loading, trying again after the rest of the indicators.");
        } else {
            self.loading_text("encountered errors while loading.");
        }

        self.num_tries += 1;
    };
};

$.fn.asyncIndicators = function (options) {
    this.each(function(i, v) {
        var viewModel = new MVISIndicatorTable(options);
        ko.applyBindings(viewModel, $(this).get(i));
        viewModel.init();
    });
};
