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
                if ($('#ready_'+d.download_id).length == 0) {
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
                if (a===self.xmlns_formdesigner || a.indexOf('.org') > 0)
                    return b.substring(0,31);
            }
            b = b.substr(0,14);
            a = a.substr(0,28-b.length);
            return a+" > "+b;
        };

    self.updateSelectedExports = function (data, event) {
        var $checkbox = $(event.srcElement);
        var add_to_list = ($checkbox.attr('checked') === 'checked'),
            downloadButton = $checkbox.parent().parent().parent().find('.dl-export');
        if (add_to_list) {
            $checkbox.parent().find('.label').removeClass('label-info').addClass('label-success');
            self.selected_exports.push(downloadButton);
        } else {
            $checkbox.parent().find('.label').removeClass('label-success').addClass('label-info');
            self.selected_exports.splice(self.selected_exports().indexOf(downloadButton), 1);
        }
    };

    self.requestBulkDownload = function(data, event) {
        resetModal("Bulk "+self.bulk_download_notice_text, false);
        var prepareExport = new Object();
        if (self.is_custom)
            prepareExport = new Array();

        for (var i in self.selected_exports()) {
            var curExpButton = self.selected_exports()[i];
            var _id = curExpButton.data('appid') || curExpButton.data('exportid'),
                xmlns = curExpButton.data('xmlns'),
                module = curExpButton.data('modulename'),
                export_type = curExpButton.data('exporttype'),
                form = curExpButton.data('formname');

            var sheetName = "sheet";
            if (self.is_custom)
                sheetName = curExpButton.parent().parent().find('.sheetname').val();
            else
                sheetName = getSheetName(module, form, xmlns);

            var export_tag;
            if (self.is_custom)
                export_tag = {
                    domain: self.domain,
                    xmlns: xmlns,
                    sheet_name: sheetName,
                    export_id: _id,
                    export_type: export_type
                };
            else
                export_tag = [self.domain, xmlns, sheetName];

            if (!_id)
                _id = "unknown_application";

            if (self.is_custom)
                prepareExport.push(export_tag)
            else {
                if (!prepareExport.hasOwnProperty(_id))
                    prepareExport[_id] = new Array();
                prepareExport[_id].push(export_tag);
            }
        }
        var downloadUrl = self.bulkDownloadUrl +
            "?"+self.exportFilters +
            "&export_tags="+encodeURIComponent(JSON.stringify(prepareExport)) +
            "&is_custom="+self.is_custom +
            "&async=true";

        $.getJSON(downloadUrl, updateModal);
    };

    self.requestDownload = function(data, event) {
        var $button = $(event.srcElement);
        var modalTitle = $button.data('formname') || $button.data('xmlns');
        var downloadUrl = self.downloadUrl || $button.data('dlocation');

        if ($button.data('modulename'))
            modalTitle  = $button.data('modulename')+" > "+modalTitle;
        resetModal("'"+modalTitle+"'", true);

        downloadUrl = downloadUrl +
            "?"+self.exportFilters+
            '&export_tag=["'+self.domain+'","'+$button.data('xmlns')+'","'+$button.data('formname')+'"]' +
            '&filename='+$button.data('formname') +
            '&async=true';
        if (!self.is_custom)
            downloadUrl = downloadUrl+'&app_id='+$button.data('appid');

        $.getJSON(downloadUrl, updateModal);
    };

    self.checkCustomSheetNameLength = function(data, event) {
        var $input = $(event.srcElement);
        var valLength = $input.val().length;
        return (valLength < 31 || event.keyCode == 8);
    };
    self.updateCustomSheetNameCharacterCount = function (data, event) {
        var $input = $(event.srcElement);
        $input.parent().find('.label').text($input.val().length);
        return true;
    };
    self.toggleSelectAllExports = function (data, event) {
        var $toggleBtn = $(event.srcElement),
            check_class = (self.is_custom) ? '.select-custom' : '.select-bulk';
        if ($toggleBtn.data('all'))
            $.each($(check_class), function () {
                $(this).attr('checked', true);
                self.updateSelectedExports({}, {srcElement: this})
            });
        else
            $.each($(check_class), function () {
                $(this).attr('checked', false);
                self.updateSelectedExports({}, {srcElement: this})
            });
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

ko.bindingHandlers.updateCustomSheetName = {
    init: function(element, valueAccessor) {
        var value = valueAccessor()();
        var originalName = $(element).val();
        var MAX_LENGTH = 31;
        if (originalName.length > MAX_LENGTH) {
            $(element).val(originalName.substring(0,MAX_LENGTH));
            $(element).data('shortened', true);
        } else {
            $(element).parent().find('.label').text(originalName.length);
        }
    },
    update: function(element, valueAccessor) {
        var value = valueAccessor()();
        var $parentRow = $(element).parent().parent().parent();
        if($parentRow.find('.select-custom').attr('checked') === 'checked')
            $(element).parent().fadeIn();
        else
            $(element).parent().fadeOut();
    }
};


