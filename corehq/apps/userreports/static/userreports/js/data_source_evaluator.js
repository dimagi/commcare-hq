/* globals hqDefine */
hqDefine('userreports/js/data_source_evaluator', function () {
    var DataSourceModel = function (submitUrl) {
        var self = this;
        self.submitUrl = submitUrl;
        self.documentsId = ko.observable();
        self.dataSourceId = ko.observable();
        self.uiFeedback = ko.observable();
        self.columns = ko.observable();
        self.rows = ko.observableArray();
        self.loading = ko.observable(false);

        self.evaluateDataSource = function() {
            self.uiFeedback("");
            if (!self.documentsId()) {
                self.uiFeedback("Please enter a document ID.");
            }
            else {
                self.loading(true);
                $.post({
                    url: self.submitUrl,
                    data: {
                        docs_id: self.documentsId(),
                        data_source: self.dataSourceId(),
                    },
                    success: function (data) {
                        var rows = [];
                        data.rows.forEach(function(row) {
                            var tableRow = [];
                            data.columns.forEach(function(column) {
                                tableRow.push(row[column]);
                            });
                            rows.push(tableRow);
                        });
                        self.columns(data.columns);
                        self.rows(rows);
                        self.loading(false);
                    },
                    error: function (data) {
                        self.loading(false);
                        self.uiFeedback("<strong>Failure!:</strong> " + data.responseJSON.error);
                    },
                });
            }
        };
    };
    return {DataSourceModel: DataSourceModel};
});
