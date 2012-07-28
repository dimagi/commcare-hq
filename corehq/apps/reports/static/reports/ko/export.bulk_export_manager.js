var BulkExportManager = function (o) {
    var self = this;
    self.selected_exports = ko.observableArray();
    self.export_type = o.export_type || "form";
    self.is_custom = o.is_custom || false;
    self.domain = o.domain;

    self.updateSelectedExports = function (data, event) {
        console.log(data);
        var $checkbox = $(event.srcElement);
        var add_to_list = ($checkbox.attr('checked') === 'checked'),
            downloadButton = $checkbox.parent().parent().find('.export-action-download');
        if (add_to_list) {
            console.log(downloadButton);
            self.selected_exports.push(downloadButton);
        } else {
            self.selected_exports.splice(self.selected_exports().indexOf(downloadButton), 1)
        }
        console.log(self.selected_exports());
    };

    self.requestBulkDownload = function(data, event) {
        console.log("requesting bulk download");
    };
};

