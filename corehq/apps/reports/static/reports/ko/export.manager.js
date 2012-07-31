var ExportManager = function (o) {
    var self = this;
    self.selected_exports = ko.observableArray();
    self.export_type = o.export_type || "form";
    self.is_custom = o.is_custom || false;

    self.domain = o.domain;
    self.downloadUrl = o.downloadUrl;
    self.bulkDownloadUrl = o.bulkDownloadUrl;
    self.exportFilters = o.exportFilters;

    self.exportModal = o.modal || "#export-download-status";
    self.$modal = $(self.exportModal);
    self.exportModalLoading = o.loadingIndicator || '.loading-indicator';
    self.exportModalLoadedData = o.loadedData || '.loaded-data';

    self.bulk_download_notice_text = (self.is_custom) ?
        "Custom Form Exports" :
        "Full Form Exports";

    self.xmlns_formdesigner = o.xmlns_formdesigner || 'formdesigner';

    var resetModal = function (modal_title, newLine) {
            self.$modal.find(self.exportModalLoading).removeClass('hide');
            self.$modal.find(self.exportModalLoadedData).empty();
            var $title = self.$modal.find('.modal-header h3 span');
            $title.text(modal_title);
            if (newLine)
                $title.attr('style', 'display: block;');
            else
                $title.attr('style', '');

        },
        updateModal = function(d) {
            var autoRefresh = '';
            var pollDownloader = function () {
                if ($('#ready_'+d.download_id).length == 0)
                {
                    $.get(d.download_url, function(data) {
                        self.$modal.find(self.exportModalLoadedData).html(data);
                    });
                } else {
                    self.$modal.find(self.exportModalLoading).addClass('hide');
                    clearInterval(autoRefresh);
                }
            };
            $(self.exportModal).on('hide', function () {
                clearInterval(autoRefresh);
            });
            autoRefresh = setInterval(pollDownloader, 2000);
        },
        getSheetName = function(module, form, xmlns) {
            var a = module,
                b = form;
            if (!(a && b)) {
                var parts = xmlns.split('/');
                a = parts[parts.length-2];
                b = parts[parts.length-1];
                if (a===self.xmlns_formdesigner)
                    return b.substring(0,31);
            }
            b = b.substr(0,14);
            a = a.substr(0,28-b.length);
            return a+" > "+b;
        };

    self.updateSelectedExports = function (data, event) {
        var $checkbox = $(event.srcElement);
        var add_to_list = ($checkbox.attr('checked') === 'checked'),
            downloadButton = $checkbox.parent().parent().find('.dl-export');
        if (add_to_list)
            self.selected_exports.push(downloadButton);
        else
            self.selected_exports.splice(self.selected_exports().indexOf(downloadButton), 1);
    };

    self.requestBulkDownload = function(data, event) {
        console.log("requesting bulk download");
        resetModal("Bulk "+self.bulk_download_notice_text, false);

        var prepareExport = new Object();
        if (self.is_custom)
            prepareExport = new Array();

        for (var i in self.selected_exports()) {
            var curExpButton = self.selected_exports()[i];
            var _id = curExpButton.data('appid') || curExpButton.data('exportid'),
                xmlns = curExpButton.data('xmlns'),
                module = curExpButton.data('modulename'),
                form = curExpButton.data('formname');
            var sheetName = getSheetName(module, form, xmlns);
            var schema_index = [self.domain, xmlns, sheetName];

            if (!_id)
                _id = "unknown_application";

            if (self.is_custom) {
                prepareExport.push(schema_index)
            } else {
                if (!prepareExport.hasOwnProperty(_id))
                    prepareExport[_id] = new Array();
                prepareExport[_id].push(schema_index);
            }
        }
        var downloadUrl = self.bulkDownloadUrl +
            "?"+self.exportFilters +
            "&export_tags="+encodeURIComponent(JSON.stringify(prepareExport)) +
            "&is_custom="+self.is_custom +
            "&async=true";

        $.getJSON(downloadUrl, updateModal);
        console.log(prepareExport);
    };


    self.requestDownload = function(data, event) {
        var $button = $(event.srcElement);
        resetModal("'"+($button.data('appname') || "Form: ")+$button.data('formname')+"'", true);
        var downloadUrl = self.downloadUrl || $button.data('dlocation');
        downloadUrl = downloadUrl +
            "?"+self.exportFilters+
            '&export_tag=["'+self.domain+'","'+$button.data('xmlns')+'","'+$button.data('formname')+'"]' +
            '&filename='+$button.data('formname') +
            '&async=true';
        if (!self.is_custom)
            downloadUrl = downloadUrl+'&app_id='+$button.data('appid');
        console.log(downloadUrl);

        $.getJSON(downloadUrl, updateModal);
    };

};

ko.bindingHandlers.showBulkExportNotice = {
    update: function(element, valueAccessor) {
        var value = valueAccessor()();
        if (value.length > 0)
            $(element).fadeIn();
        else
            $(element).fadeOut();
    }
};


