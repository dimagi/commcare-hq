hqDefine("commtrack/js/stock_levels", [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
], function(
    $,
    ko,
    initialPageData
) {
    var rowModel = function(data, keys) {
        var self = {};
        self.errors = ('form_errors' in data) ? data.form_errors : {};
        self.num_columns = keys.length;

        self.data = {};
        keys.forEach(function(key) {
            self.data[key] = ko.observable(data[key]);
        });

        return self;
    };

    var tableModel = function(rowSpec, rawRows) {
        var self = {};
        self.keys = rowSpec.map(function(spec) {
            return spec['key'];
        });
        self.rows = ko.observableArray();

        for (var i = 0; i < rawRows.length; i++) {
            self.rows.push(rowModel(rawRows[i], self.keys));
        }

        self.serialize = function() {
            return self.rows().map(function(row) {
                var serializedRow = {};
                self.keys.forEach(function(key) {
                    serializedRow[key] = row.data[key]();
                });
                return serializedRow;
            });
        };

        self.submit_table = function(form) {
            var tableForm = $("#table-form")
                .attr("action", form.action);
            $('<input type="hidden">')
                .attr('name', 'child_form_data')
                .attr('value', JSON.stringify(self.serialize()))
                .appendTo(tableForm);
            return true;
        };

        return self;
    };

    $(function() {
        var formContext = initialPageData.get("form_context");
        $('#table-form').koApplyBindings(tableModel(formContext.row_spec, formContext.rows));
    });
});
