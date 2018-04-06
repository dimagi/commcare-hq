hqDefine("commtrack/js/stock_levels", function() {
    $(function() {
        function Row(data, keys) {
            var self = this;
            self.errors = ('form_errors' in data) ? data.form_errors : {};
            self.num_columns = keys.length;

            self.data = {};
            keys.forEach(function(key) {
                self.data[key] = ko.observable(data[key]);
            });
        }

        function TableModel(row_spec, raw_rows) {
            var self = this;
            self.keys = row_spec.map(function(spec) {
                return spec['key'];
            });
            self.rows = ko.observableArray();

            for (var i = 0; i < raw_rows.length; i++) {
                self.rows.push(new Row(raw_rows[i], self.keys));
            }

            self.serialize = function() {
                return self.rows().map(function(row) {
                    var serialized_row = {};
                    self.keys.forEach(function(key) {
                        serialized_row[key] = row.data[key]();
                    });
                    return serialized_row;
                });
            };

            self.submit_table = function(table_form) {
                var tableForm = $("<form>")
                    .attr("method", "POST")
                    .attr("action", table_form.action);
                $('<input type="hidden">')
                    .attr('name', 'child_form_data')
                    .attr('value', JSON.stringify(self.serialize()))
                    .appendTo(tableForm);
                $("{% csrf_token %}").appendTo(tableForm);
                tableForm.appendTo("body");
                tableForm.submit();
            };
        }

        var formContext = hqImport("hqwebapp/js/initial_page_data").get("form_context"),
            tableModel = new TableModel(formContext.row_spec, formContext.rows);
        ko.applyBindings(tableModel, $('#table-form').get(0));
    });

});
