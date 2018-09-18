var CHWIndicatorTable = function (options) {
    'use strict';
    var self = this;
    self.qIndex = -1;

    self.indicators = _.map(options.indicators, function(indicator){
        return new CHWIndicator(indicator);
    });

    self.init = function () {
        var _queue = new window.mvp.MVPIndicatorQueue(
            options.indicators.length, function (ind, fnNext) {
                return self.indicators[ind].updateIndicator()
                    .done(fnNext)
                    .fail(fnNext);
            }
        );
        _queue.start();
    };

};

var CHWIndicator = function (options) {
    'use strict';
    var self = this;

    self.slug = options.slug;
    self.load_url = options.load_url;
    self.index = options.index;

    self.is_loaded = false;

    self.data = null;
    self.average = null;
    self.median = null;
    self.total = null;
    self.std = null;

    self.updateIndicator = function () {
        var _updater = new window.mvp.MVPIndicatorUpdater(
            self.load_url, self.loadSuccess, self.loadError
        );
        _updater.start();
        return _updater.d;
    };

    self.loadSuccess = function (data) {
        if (!data.error) {
            self.is_loaded = true;
            self.data = data.data;
            self.user_indices = data.user_indices;
            self.average = data.average;
            self.total = data.total;
            self.median = data.median;
            self.std = data.std;
            self.apply_updates();
        } else {
            self.mark_as_error();
        }
    };

    self.loadError = function (error) {
        self.mark_as_error();
    };

    self.mark_as_error = function () {
        $('.status-' + self.slug).replaceWith('<i class="fa fa-exclamation-triangle"></i>');
    };

    self.apply_updates = function () {
        var slug = hqImport("hqwebapp/js/initial_page_data").get("js_options").slug,
            datatable = $('#report_table_' + slug + '.datatable').dataTable(),
            new_data = datatable.fnGetData();
        for (var user_id in self.data) {
            if (self.data.hasOwnProperty(user_id) &&
                self.user_indices.hasOwnProperty(user_id)) {
                var formatted_data = self.data[user_id];
                var user_index = self.user_indices[user_id];
                new_data[user_index][self.index+1] = formatted_data;
            }
        }
        datatable.fnClearTable();
        datatable.fnAddData(new_data);
        datatable.fnAdjustColumnSizing(true);

        $('.dataTables_scrollFoot .total.'+self.slug).html(self.total);
        $('.dataTables_scrollFoot .average.'+self.slug).html(self.average);
        $('.dataTables_scrollFoot .median.'+self.slug).html(self.median);
        $('.dataTables_scrollFoot .std.'+self.slug).html(self.std);
    };
};
