var CHWIndicatorTable = function (options) {
    'use strict';
    var self = this;

    self.indicators = _.map(options.indicators, function(indicator){
        return new CHWIndicator(indicator);
    });

    self.init = function () {
        // initialize all the indicators
        for (var i=0; i < self.indicators.length; i++) {
            self.indicators[i].init();
        }
    };

};

var CHWIndicator = function (options) {
    'use strict';
    var self = this;

    self.slug = options.slug;
    self.load_url = options.load_url;
    self.index = options.index;

    self.is_loaded = false;
    self.num_tries = 0;

    self.data = null;
    self.average = null;
    self.median = null;
    self.std = null;

    self.init = function () {
        queue.add(self);
    };

    self.load_success = function (data) {
        if (!data.error) {
            self.is_loaded = true;
            self.data = data.data;
            self.user_indices = data.user_indices;
            self.average = data.average;
            self.median = data.median;
            self.std = data.std;
            self.apply_updates();
        }
        queue.next(false);
    };

    self.load_error = function (error) {
        console.log("there was an error");
        console.log(error);
        queue.next(false);
        if (self.num_tries <= 3) {
            console.log("trying again");
            // show retry message
            queue.add(self);
        } else {
            // show error message
        }
        self.num_tries += 1;
    };

    self.apply_updates = function () {
        console.log("\nNEW");
        console.log(self.index);
        console.log('--');
        var new_data = reportTables.datatable.fnGetData();
        for (var user_id in self.data) {
            if (self.data.hasOwnProperty(user_id) &&
                self.user_indices.hasOwnProperty(user_id)) {
                var formatted_data = self.data[user_id];
                var user_index = self.user_indices[user_id];
                new_data[user_index][self.index+1] = formatted_data;
//                $('.'+user_id+' .'+self.slug).html(formatted_data);
            }
        }
        reportTables.datatable.fnClearTable();
        reportTables.datatable.fnAddData(new_data);
        reportTables.datatable.fnAdjustColumnSizing(true);

//        console.log(reportTables.datatable.fnGetData());
//        $('.average.'+self.slug).html(self.average);
//        $('.median.'+self.slug).html(self.median);
//        $('.std.'+self.slug).html(self.std);
    };
};
