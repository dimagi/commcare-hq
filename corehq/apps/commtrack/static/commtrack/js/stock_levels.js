hqDefine("commtrack/js/stock_levels", function() {
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
            var tableForm = $("<form>")
                .attr("method", "POST")
                .attr("action", form.action);
            $('<input type="hidden">')
                .attr('name', 'child_form_data')
                .attr('value', JSON.stringify(self.serialize()))
                .appendTo(tableForm);
            $("{% csrf_token %}").appendTo(tableForm);
            tableForm.appendTo("body");
            tableForm.submit();
        };

        return self;
    };

    $(function() {
        var formContext = hqImport("hqwebapp/js/initial_page_data").get("form_context");
        ko.applyBindings(tableModel(formContext.row_spec, formContext.rows), $('#table-form').get(0));
    });

});
