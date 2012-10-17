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

    self.sheet_names = ko.observable(new Object());

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
                    }).error(function () {
                        self.$modal.find(self.exportModalLoading).addClass('hide');
                        self.$modal.find(self.exportModalLoadedData).html('<p class="alert alert-error">Oh no! Your download was unable to be completed. We have been notified and are already hard at work solving this issue.</p>');
                        clearInterval(autoRefresh);
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
        displayModalError = function(error_text) {
            var $error = $('<p class="alert alert-error" />');
            $error.text(error_text);
            self.$modal.find(self.exportModalLoadedData).html($error);
            self.$modal.find(self.exportModalLoading).addClass('hide');
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
            return getFormattedSheetName(a,b);
        };

    self.updateSelectedExports = function (data, event) {
        var $checkbox = $(event.srcElement || event.currentTarget);
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
            if (self.is_custom) {
                var $sheetNameElem = curExpButton.parent().parent().find('.sheetname');
                if($sheetNameElem.data('duplicate'))
                    break;
                sheetName = curExpButton.parent().parent().find('.sheetname').val();
            } else
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
                prepareExport.push(export_tag);
            else {
                if (!prepareExport.hasOwnProperty(_id))
                    prepareExport[_id] = new Array();
                prepareExport[_id].push(export_tag);
            }
        }

        if (self.is_custom && prepareExport.length == 0) {
            displayModalError('No valid sheets were available for Custom Bulk Export. Please check for duplicate sheet names.');
            return;
        }

        var downloadUrl = self.bulkDownloadUrl +
            "?"+self.exportFilters +
            "&export_tags="+encodeURIComponent(JSON.stringify(prepareExport)) +
            "&is_custom="+self.is_custom +
            "&async=true";

        $.getJSON(downloadUrl, updateModal);
    };

    self.requestDownload = function(data, event) {
        var $button = $(event.srcElement || event.currentTarget);
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

    self.requestCaseDownload = function(data, event) {
        var $button = $(event.srcElement || event.currentTarget);
        var downloadUrl = self.downloadUrl || $button.data('dlocation');
        var modalTitle = "Case List";
        resetModal(modalTitle, true);

        downloadUrl += '?'+self.exportFilters;
        downloadUrl += '&include_closed=' + $('#include-closed-select').val();
        downloadUrl += '&async=true'

        $.getJSON(downloadUrl, updateModal);
    };

    self.checkCustomSheetNameLength = function(data, event) {
        var src = event.srcElement || event.currentTarget;
        var $input = $(src);
        var valLength = $input.val().length;
        return (valLength < 31 || event.keyCode == 8 || (src.selectionEnd-src.selectionStart) > 0);
    };

    self.updateCustomSheetNameCharacterCount = function (data, event) {
        var $input = $(event.srcElement || event.currentTarget);
        if ($input.data('exportid')) {
            var new_names = self.sheet_names();
            new_names[$input.data('exportid')] = $input.val();
            self.sheet_names(new_names);
        }
        $input.parent().find('.sheetname-count').text($input.val().length);
        return true;
    };

    self.toggleSelectAllExports = function (data, event) {
        var $toggleBtn = $(event.srcElement || event.currentTarget),
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

},
    getFormattedSheetName = function (a, b) {
        b = b.substr(0, 14);
        a = a.substr(0,28-b.length);
        return a+" > "+b;
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

ko.bindingHandlers.checkForUniqueSheetName = {
    update: function(element, valueAccessor) {
        var value = valueAccessor()(),
            current_name = $(element).val(),
            $dupeNotice = $(element).parent().find('.sheetname-duplicate'),
            $parentCol = $(element).parent().parent();
        var all_names = _.toArray(value);
        if( (_.lastIndexOf(all_names, current_name) - _.indexOf(all_names, current_name)) > 0) {
            $dupeNotice.removeClass('hide');
            $parentCol.addClass('error');
            $(element).data('duplicate', true);
        } else {
            $dupeNotice.addClass('hide');
            $parentCol.removeClass('error');
            $(element).data('duplicate', false);
        }
    }
};

ko.bindingHandlers.updateCustomSheetName = {
    init: function(element, valueAccessor, allBindingsAccessor) {
        var value = valueAccessor()(),
            originalName = $(element).val(),
            MAX_LENGTH = 31,
            SPLIT_CHAR = '>';

        if (originalName.indexOf(SPLIT_CHAR) > 0 && originalName.length > MAX_LENGTH) {
            // intelligently generate a sheetname
            var splitName = originalName.split(SPLIT_CHAR);
            var formname = splitName[splitName.length-1].trim(),
                modulename = splitName[splitName.length-2].trim();
            originalName = getFormattedSheetName(modulename, formname);
            $(element).val(originalName);
        }

        if (originalName.length > MAX_LENGTH) {
            $(element).val(originalName.substring(Math.max(0, originalName.length-MAX_LENGTH),originalName.length));
        } else {
            $(element).parent().find('.sheetname-count').text(originalName.length);
        }


    },
    update: function(element, valueAccessor, allBindingsAccessor) {
        var value = valueAccessor()(),
            allSheetNames = allBindingsAccessor().checkForUniqueSheetName;
        var $parentRow = $(element).parent().parent().parent(),
            exportID = $(element).data('exportid');
        if($parentRow.find('.select-custom').attr('checked') === 'checked') {
            $(element).parent().fadeIn();
            if(exportID)
                allSheetNames()[exportID] = $(element).val();
        } else {
            $(element).parent().fadeOut();
            if(exportID)
                delete allSheetNames()[exportID];
        }
    }
};


