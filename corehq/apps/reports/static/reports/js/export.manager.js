// TODO - after old usage is removed, refactor into two separate entities
var ExportManager = function (o) {
    var self = this;
    self.isNewExporter = o.is_new_exporter || false;
    self.selected_exports = ko.observableArray();
    self.export_type = o.export_type || "form";
    self.is_custom = o.is_custom || false;
    self.is_deid_form_report = o.is_deid_form_report || false;

    self.format = o.format || "csv";
    self.domain = o.domain;
    self.downloadUrl = o.downloadUrl;
    self.bulkDownloadUrl = o.bulkDownloadUrl;
    self.exportFilters = o.exportFilters;
    self.jsonExportFilters = o.jsonExportFilters;

    self.exportModal = o.modal || "#export-download-status";
    self.$modal = $(self.exportModal);
    self.exportModalLoading = o.loadingIndicator || '.loading-indicator';
    self.exportModalLoadedData = o.loadedData || '.loaded-data';

    self.bulk_download_notice_text = self.isNewExporter ? (
        o.bulk_download_notice_text || ''): (self.is_custom ?
        "Custom Form Exports" : "Full Form Exports"
    );

    self.xmlns_formdesigner = o.xmlns_formdesigner || 'formdesigner';

    self.sheet_names = ko.observable(new Object());

    self.selectedExportsData = o.selectedExportsData || {};

    if(self.isNewExporter) {
        self.bulkDownloadPageUrlRoot = o.bulkDownloadPageUrlRoot;
        self.bulkDownloadPageUrl = ko.computed(function() {
            return self.bulkDownloadPageUrlRoot + '?' + self.selected_exports().map(
                function(export_id) { return "export_id=" + export_id; }
            ).join('&');
        });
    }

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
        /**
         * Expected params keys:
         *  - data (required)
         *  - isBulkDownload
         *  - xmlns
         *  - exportName
         * the two optional keys are used for google analytics.
         * @param params
         */
        updateModal = function(params) {
            var autoRefresh = true;
            var pollDownloader = function () {
                if (autoRefresh && $('#ready_'+params.data.download_id).length === 0) {
                    $.get({
                        url: params.data.download_url,
                        success: function(data) {
                            self.$modal.find(self.exportModalLoadedData).html(data);
                            self.setUpEventTracking({
                                xmlns: params.xmlns,
                                isBulkDownload: params.isBulkDownload,
                                exportName: params.exportName,
                                isMultimedia: params.isMultimedia
                            });
                            if (autoRefresh) {
                                setTimeout(pollDownloader, 2000);
                            }
                        },
                        error: function () {
                            self.$modal.find(self.exportModalLoading).addClass('hide');
                            self.$modal.find(self.exportModalLoadedData).html('<p class="alert alert-error">' +
                                gettext('Oh no! Your download was unable to be completed. ' +
                                'We have been notified and are already hard at work solving this issue.') +
                                '</p>');
                            autoRefresh = false;
                        },
                    });
                } else {
                    self.$modal.find(self.exportModalLoading).addClass('hide');
                    autoRefresh = false;
                }
            };
            $(self.exportModal).on('hide', function () {
                autoRefresh = false;
            });
            pollDownloader();
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

    self.setUpEventTracking = function(params) {
        params = params || {};
        var downloadButton = self.$modal.find(self.exportModalLoadedData).find("a.btn.btn-primary").first();
        if (downloadButton.length) {

            if (params.isMultimedia) {
                var action = self.is_custom ? "Download Custom Form Multimedia" : "Download Form Multimedia";
                gaTrackLink(downloadButton, "Form Exports", action, params.exportName);
                return;
            }

            // Device reports event
            // (This is a bit of a special case due to its unique "action" and "label"
            if (params.xmlns == "http://code.javarosa.org/devicereport") {
                gaTrackLink(downloadButton, "Form Exports", "Download Mobile Device Log", "Export Mobile Device Log");
            }

            var label;
            if (self.export_type == "case"){

                if (params.isBulkDownload){
                    label = $('#include-closed-select').val() == "true" ? "all" : "all open";
                    gaTrackLink(downloadButton, "Download Case Export", "Download Raw Case Export", label);
                }

            } else if (self.export_type == "form"){
                var category = "Download Form Export";


                var action = "Download Raw Form Export";
                label = params.isBulkDownload ? "bulk" : params.xmlns;
                if (self.is_deid_form_report){
                    action = "Download Deidentified Form Export";
                    label = params.isBulkDownload ? label : params.exportName;
                } else if (self.is_custom){
                    action = "Download Custom Form Export";
                    label = params.isBulkDownload ? label : params.exportName;
                }

                gaTrackLink(downloadButton, category, action, label);

            }
        }
    };

    if(!self.isNewExporter) {
        self.updateSelectedExports = function (data, event) {
            var $checkbox = $(event.srcElement || event.currentTarget);
            var add_to_list = $checkbox.prop('checked'),
                downloadButton = $checkbox.parent().parent().parent().find('.dl-export');
            if (add_to_list) {
                $checkbox.parent().find('.label').removeClass('label-info').addClass('label-success');
                self.selected_exports.push(downloadButton);
            } else {
                $checkbox.parent().find('.label').removeClass('label-success').addClass('label-info');
                self.selected_exports.splice(self.selected_exports().indexOf(downloadButton), 1);
            }
        };
    } else {
        self.updateSelectedExports = function (data, event) {
            var $checkbox = $(event.srcElement || event.currentTarget);
            var add_to_list = $checkbox.prop('checked'),
                export_id = $checkbox.attr('value');
            if (add_to_list) {
                $checkbox.parent().find('.label').removeClass('label-info').addClass('label-success');
                self.selected_exports.push(export_id);
            } else {
                $checkbox.parent().find('.label').removeClass('label-success').addClass('label-info');
                self.selected_exports.splice(self.selected_exports().indexOf(export_id), 1);
            }
        };
    }

    self.downloadExport = function(params) {
        var displayDownloadError = function (response) {
            displayModalError(gettext('Sorry, something unexpected went wrong and your download ' +
                'could not be completed. Please try again and report an issue if the problem ' +
                'persists.')
            );
        };
        $.ajax({
            dataType: 'json',
            url: params.downloadUrl,
            success: function(data){
                updateModal({
                    data: data,
                    xmlns: params.xmlns,
                    isBulkDownload: params.isBulkDownload,
                    isMultimedia: params.isMultimedia,
                    exportName: params.exportName
                });
            },
            error: displayDownloadError
        });
    };

    self.downloadBulkExport = function(downloadUrl, data) {
        var displayDownloadError = function (response) {
            displayModalError(gettext('Sorry, something unexpected went wrong and your download ' +
                    'could not be completed. Please try again and report an issue if the problem ' +
                    'persists.')
            );
        };
        $.ajax({
            dataType: 'json',
            url: downloadUrl,
            type: 'POST',
            data: data,
            traditional: true,
            success: function(respData){
                updateModal({
                    data: respData,
                    xmlns: null,
                    isBulkDownload: true
                });
            },
            error: displayDownloadError
        });
    };
        
    self.requestBulkDownload = function(data, event) {
        resetModal("Bulk "+self.bulk_download_notice_text, false);
        var prepareExport = new Object();
        if (self.is_custom)
            prepareExport = new Array();

        if(self.isNewExporter) {
            for (var export_id in self.selectedExportsData) {
                var export_data = self.selectedExportsData[export_id];
                var xmlns = export_data.xmlns,
                    module = export_data.modulename,
                    export_type = export_data.exporttype,
                    form = export_data.formname,
                    _id = export_id;

                var sheetName = getSheetName(module, form, xmlns);

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
                        prepareExport[_id] = [];
                    prepareExport[_id].push(export_tag);
                }
            }
        } else {
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
        }


        if (self.is_custom && prepareExport.length == 0) {
            displayModalError(gettext('No valid sheets were available for Custom Bulk Export. ' +
                                      'Please check for duplicate sheet names.'));
            return;
        }

        var params = {
            'export_tags': JSON.stringify(prepareExport),
            'is_custom': self.is_custom,
            'async': true
        };

        for(var filter in self.jsonExportFilters) {
            if(self.jsonExportFilters.hasOwnProperty(filter)) {
                params[filter] = self.jsonExportFilters[filter];
            }
        }
        self.downloadBulkExport(self.bulkDownloadUrl, params);
    };

    self._requestDownload = function(event, options) {
        var $button = $(event.srcElement || event.currentTarget);
        var downloadUrl = self.downloadUrl || $button.data('dlocation');
        var xmlns = $button.data('xmlns');
        resetModal("'" + options.modalTitle + "'", true);
        var format = self.format;
        var formName = $.trim($button.data('formname'));
        var fileName = encodeURIComponent(formName);
        if ($button.data('format')) {
            format = $button.data('format');
        }
        downloadUrl = downloadUrl +
            "?" + self.exportFilters +
            '&async=true' +
            '&export_tag=["'+self.domain+'","'+xmlns+'","' + fileName +'"]' +
            '&format=' + format +
            '&filename=' + fileName;

        for (var k in options.downloadParams) {
            if (options.downloadParams.hasOwnProperty(k)) {
                var v = options.downloadParams[k];
                downloadUrl += '&' + k + '=' + v;
            }
        }
        self.downloadExport({
            downloadUrl: downloadUrl,
            xmlns: xmlns,
            isBulkDownload: options.isBulkDownload,
            exportName: formName || xmlns
        });
    };

    self.requestDownload = function(data, event) {
        var $button = $(event.srcElement || event.currentTarget);
        var formNameOrXmlns = $button.data('formname') || $button.data('xmlns');
        var modalTitle = formNameOrXmlns;
        if ($button.data('modulename')) {
            modalTitle  = $button.data('modulename') + " > " + modalTitle;
        }
        var downloadParams = {};
        if (!self.is_custom) {
            downloadParams.app_id = $button.data('appid');
        }
        return self._requestDownload(event, {
            modalTitle: modalTitle,
            downloadParams: downloadParams,
            isBulkDownload: false
        });
    };

    self.requestCaseDownload = function(data, event) {
        return self._requestDownload(event, {
            modalTitle: "Case List",
            downloadParams: {
                include_closed: $('#include-closed-select').val()
            },
            isBulkDownload: true
        });
    };

    self.requestMultimediaDownload = function(data, event){
        var $button = $(event.srcElement || event.currentTarget),
            xmlns = $button.data('xmlns'),
            downloadUrl = $button.data('downloadurl') + '&xmlns=' + xmlns,
            title = $button.data('modulename');

        title = $button.data('formname').length ? title + " > " + $button.data('formname') : title;

        resetModal("'" + title + "' (multimedia)", true);
        self.downloadExport({
            downloadUrl: downloadUrl,
            xmlns: xmlns,
            isMultimedia: true,
            exportName: xmlns
        });
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

    if(!self.isNewExporter) {
        self.toggleSelectAllExports = function (data, event) {
            var $toggleBtn = $(event.srcElement || event.currentTarget),
                check_class = (self.is_custom) ? '.select-custom' : '.select-bulk';
            if ($toggleBtn.data('all'))
                $.each($(check_class), function () {
                    $(this).prop('checked', true);
                    self.updateSelectedExports({}, {srcElement: this});
                });
            else
                $.each($(check_class), function () {
                    $(this).prop('checked', false);
                    self.updateSelectedExports({}, {srcElement: this});
                });
        };
    } else {
        self.toggleSelectAllExports = function (data, event) {
            var $toggleBtn = $(event.srcElement || event.currentTarget),
                check_class = '.select-export';
            if ($toggleBtn.data('all')) {
                $.each($(check_class), function () {
                    $(this).prop('checked', true);
                    self.updateSelectedExports({}, {srcElement: this});
                });
            } else {
                $.each($(check_class), function () {
                    $(this).prop('checked', false);
                    self.updateSelectedExports({}, {srcElement: this});
                });
            }
        };
    }


},
    getFormattedSheetName = function (a, b) {
        // force to string
        a = '' + a;
        b = '' + b;
        b = b.substr(0, 14);
        a = a.substr(0, 28 - b.length);
        return a + " > " + b;
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
        if($parentRow.find('.select-custom').prop('checked')) {
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
