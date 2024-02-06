hqDefine("reports/js/config.dataTables.bootstrap", [
    'jquery',
    'underscore',
    'analytix/js/google',
    'datatables.bootstrap',
], function (
    $,
    _,
    googleAnalytics
) {
    var HQReportDataTables = function (options) {
        var self = {};
        self.dataTableElem = options.dataTableElem || '.datatable';
        self.paginationType = options.paginationType || 'bs_normal';
        self.forcePageSize = options.forcePageSize || false;
        self.defaultRows = options.defaultRows || 10;
        self.startAtRowNum = options.startAtRowNum || 0;
        self.showAllRowsOption = options.showAllRowsOption || false;
        self.aoColumns = options.aoColumns;
        self.autoWidth = (options.autoWidth !== undefined) ? options.autoWidth : true;
        self.defaultSort = (options.defaultSort !== undefined) ? options.defaultSort : true;
        self.customSort = options.customSort || null;
        self.ajaxParams = options.ajaxParams || {};
        self.ajaxSource = options.ajaxSource;
        self.ajaxMethod = options.ajaxMethod || 'GET';
        self.loadingText = options.loadingText || "<i class='fa fa-spin fa-spinner'></i> " + gettext("Loading");
        self.loadingTemplateSelector = options.loadingTemplateSelector;
        if (self.loadingTemplateSelector !== undefined) {
            var loadingTemplate = _.template($(self.loadingTemplateSelector).html() || self.loadingText);
            self.loadingText = loadingTemplate({});
        }
        self.emptyText = options.emptyText || gettext("No data available to display. " +
                                                      "Please try changing your filters.");
        self.errorText = options.errorText || "<span class='label label-danger'>" + gettext("Sorry!") + "</span> " +
                         gettext("There was an error with your query, it has been logged, please try another query.");
        self.badRequestErrorText = options.badRequestErrorText || options.errorText ||
                                   "<span class='label label-danger'>" + gettext("Sorry!") + "</span> " +
                                   gettext("Your search query is invalid, please adjust the formatting and try again.");
        self.fixColumns = !!(options.fixColumns);
        self.fixColsNumLeft = options.fixColsNumLeft || 1;
        self.fixColsWidth = options.fixColsWidth || 100;
        self.show_pagination = (options.show_pagination === undefined) ? true : options.bPaginate;
        self.aaSorting = options.aaSorting || null;
        // a list of functions to call back to after ajax.
        // see user configurable charts for an example usage
        self.successCallbacks = options.successCallbacks;
        self.errorCallbacks = options.errorCallbacks;
        self.includeFilter = options.includeFilter || false;
        self.datatable = null;
        self.rendered = false;

        self.render_footer_row = (function () {
            var $dataTableElem = $(self.dataTableElem);
            return function (id, row) {
                if ($dataTableElem.find('tfoot').length === 0) {
                    var $row = $dataTableElem.find('#' + id);
                    if ($row.length === 0) {
                        $row = $('<tfoot />');
                        $dataTableElem.append($row);
                    }
                    $row.html('');
                    for (var i = 0; i < row.length; i++) {
                        $row.append('<td>' + row[i] + '</td>');
                    }
                }
            };
        })();

        self.render = function () {
            if (self.rendered) {
                $(self.dataTableElem).each(function () {
                    if ($.fn.dataTable.versionCheck) {
                        // $.fn.dataTable.versionCheck does not exist prior to 1.10
                        $(this).DataTable().ajax.reload();
                    } else {
                        $(this).dataTable().fnReloadAjax();
                    }
                });
                return;
            }

            self.rendered = true;

            $('[data-datatable-highlight-closest]').each(function () {
                $(this).closest($(this).attr('data-datatable-highlight-closest')).addClass('active');
            });
            function applyBootstrapMagic() {
                $('[data-datatable-tooltip]').each(function () {
                    $(this).tooltip({
                        placement: $(this).attr('data-datatable-tooltip'),
                        title: $(this).attr('data-datatable-tooltip-text'),
                    });
                });
            }
            applyBootstrapMagic();

            var dataTablesDom = "frt<'row dataTables_control'<'col-sm-5'il><'col-sm-7 text-right'p>>";
            $(self.dataTableElem).each(function () {
                var params = {
                    sDom: dataTablesDom,
                    bPaginate: self.show_pagination,
                    sPaginationType: self.paginationType,
                    iDisplayLength: self.defaultRows,
                    bAutoWidth: self.autoWidth,
                    sScrollX: "100%",
                    bSort: self.defaultSort,
                    bFilter: self.includeFilter,
                };
                if (self.aaSorting !== null || self.customSort !== null) {
                    params.aaSorting = self.aaSorting || self.customSort;
                }

                if (self.ajaxSource) {
                    params.bServerSide = true;
                    params.bProcessing = true;
                    params.sAjaxSource = {
                        url: self.ajaxSource,
                        method: self.ajaxMethod,
                    };
                    params.bFilter = $(this).data('filter') || false;
                    self.fmtParams = function (defParams) {
                        var ajaxParams = $.isFunction(self.ajaxParams) ? self.ajaxParams() : self.ajaxParams;
                        for (var p in ajaxParams) {
                            if (_.has(ajaxParams, p)) {
                                var currentParam = ajaxParams[p];
                                if (_.isObject(currentParam.value)) {
                                    for (var j = 0; j < currentParam.value.length; j++) {
                                        defParams.push({
                                            name: currentParam.name,
                                            value: currentParam.value[j],
                                        });
                                    }
                                } else {
                                    defParams.push(currentParam);
                                }
                            }
                        }
                        return defParams;
                    };
                    params.fnServerData = function (sSource, aoData, fnCallback, oSettings) {
                        var customCallback = function (data) {
                            if (data.warning) {
                                throw new Error(data.warning);
                            }
                            var result = fnCallback(data); // this must be called first because datatables clears the tfoot of the table
                            var i;
                            if ('total_row' in data) {
                                self.render_footer_row('ajax_total_row', data['total_row']);
                            }
                            if ('statistics_rows' in data) {
                                for (i = 0; i < data.statistics_rows.length; i++) {
                                    self.render_footer_row('ajax_stat_row-' + i, data.statistics_rows[i]);
                                }
                            }
                            applyBootstrapMagic();
                            if ('context' in data) {
                                var iconPath = data['icon_path'] || $(".base-maps-data").data("icon_path");
                                hqRequire(["reports/js/maps_utils"], function (mapsUtils) {
                                    mapsUtils.load(data['context'], iconPath);
                                });
                            }
                            if (self.successCallbacks) {
                                for (i = 0; i < self.successCallbacks.length; i++) {
                                    self.successCallbacks[i](data);
                                }
                            }
                            return result;
                        };
                        oSettings.jqXHR = $.ajax({
                            "url": sSource.url,
                            "method": sSource.method,
                            "data": self.fmtParams(aoData),
                            "success": customCallback,
                            "error": function (jqXHR, textStatus, errorThrown) {
                                $(".dataTables_processing").hide();
                                if (jqXHR.status === 400) {
                                    var errorMessage = self.badRequestErrorText;
                                    if (jqXHR.responseText) {
                                        errorMessage = "<p><span class='label label-danger'>" + gettext("Sorry!") + "</span> " + jqXHR.responseText + "</p>";
                                    }
                                    $(".dataTables_empty").html(errorMessage);
                                } else {
                                    $(".dataTables_empty").html(self.errorText);
                                }
                                $(".dataTables_empty").show();
                                if (self.errorCallbacks) {
                                    for (var i = 0; i < self.errorCallbacks.length; i++) {
                                        self.errorCallbacks[i](jqXHR, textStatus, errorThrown);
                                    }
                                }
                            },
                        });
                    };
                }
                params.oLanguage = {
                    sProcessing: self.loadingText,
                    sLoadingRecords: self.loadingText,
                    sZeroRecords: self.emptyText,
                };

                params.fnDrawCallback = function (a,b,c) {
                    /* be able to set fnDrawCallback from outside here later */
                    if (self.fnDrawCallback) {
                        self.fnDrawCallback(a,b,c);
                    }
                };

                if (self.aoColumns) {
                    params.aoColumns = self.aoColumns;
                }

                if (self.forcePageSize) {
                    // limit the page size option to just the default size
                    params.lengthMenu = [self.defaultRows];
                }
                var datatable = $(this).dataTable(params);
                if (!self.datatable) {
                    self.datatable = datatable;
                }

                if (self.fixColumns) {
                    new $.fn.dataTable.FixedColumns(datatable, {
                        iLeftColumns: self.fixColsNumLeft,
                        iLeftWidth: self.fixColsWidth,
                    });
                }

                // This fixes a display bug in some browsers where the pagination
                // overlaps the footer when resizing from 10 to 100 or 10 to 50 rows
                // (perhaps other lengths are affected...unknown). This makes sure
                // that columns are redrawn on the first hit of a new length,
                // as fnAdjustColumnSizing fixes the issue and it remains fixed
                // without intervention afterward.
                self._lengthsSeen = [];
                datatable.on('length.dt', function (e, settings, length) {
                    if (self._lengthsSeen.indexOf(length) < 0) {
                        datatable.fnAdjustColumnSizing();
                        self._lengthsSeen.push(length);
                    }
                });

                var $dataTablesFilter = $(".dataTables_filter");
                if ($dataTablesFilter && $("#extra-filter-info")) {
                    if ($dataTablesFilter.length > 1) {
                        $($dataTablesFilter.first()).remove();
                        $dataTablesFilter = $($dataTablesFilter.last());
                    }
                    $("#extra-filter-info").html($dataTablesFilter);
                    $dataTablesFilter.addClass("form-search");
                    var $inputField = $dataTablesFilter.find("input"),
                        $inputLabel = $dataTablesFilter.find("label");

                    $dataTablesFilter.append($inputField);
                    $inputField.attr("id", "dataTables-filter-box");
                    $inputField.addClass("search-query").addClass('form-control');
                    $inputField.attr("placeholder", "Search...");

                    $inputLabel.attr("for", "dataTables-filter-box");
                    $inputLabel.html($('<i />').addClass("icon-search"));
                }

                var $dataTablesLength = $(self.dataTableElem).parents('.dataTables_wrapper').find(".dataTables_length"),
                    $dataTablesInfo = $(self.dataTableElem).parents('.dataTables_wrapper').find(".dataTables_info");
                if ($dataTablesLength && $dataTablesInfo) {
                    var $selectField = $dataTablesLength.find("select"),
                        $selectLabel = $dataTablesLength.find("label");

                    $dataTablesLength.append($selectField);
                    $selectLabel.remove();
                    $selectField.children().append(" per page");
                    if (self.showAllRowsOption) {
                        $selectField.append($('<option value="-1" />').text("All Rows"));
                    }
                    $selectField.addClass('form-control');
                    $selectField.on("change", function () {
                        var selectedValue = $selectField.find('option:selected').val();
                        googleAnalytics.track.event("Reports", "Changed number of items shown", selectedValue);
                    });
                }
                $(".dataTables_length select").change(function () {
                    $(self.dataTableElem).trigger('hqreport.tabular.lengthChange', $(this).val());
                });
            });
        };  // end of self.render

        return self;
    };

    $.extend($.fn.dataTableExt.oStdClasses, {
        "sSortAsc": "header headerSortAsc",
        "sSortDesc": "header headerSortDesc",
        "sSortable": "header headerSort",
    });

    // For sorting rows

    function sortSpecial(a, b, asc, convert) {
        var x = convert(a);
        var y = convert(b);

        // sort nulls at end regardless of current sort direction
        if (x === null && y === null) {
            return 0;
        }
        if (x === null) {
            return 1;
        }
        if (y === null) {
            return -1;
        }

        return (asc ? 1 : -1) * ((x < y) ? -1 : ((x > y) ?  1 : 0));
    }

    function convertNum(k) {
        var m = k.match(/title="*([-+.0-9eE]+)/);
        if (m !== null) {
            m = +m[1];
            if (isNaN(m)) {
                m = null;
            }
        }
        return m;
    }

    function convertDate(k) {
        var m = k.match(/title="*(.+)"/);
        if (m[1] === "None") {
            return null;
        }
        return new Date(m[1]);
    }

    $.fn.dataTableExt.oSort['title-numeric-asc'] = function (a, b) { return sortSpecial(a, b, true, convertNum); };

    $.fn.dataTableExt.oSort['title-numeric-desc'] = function (a, b) { return sortSpecial(a, b, false, convertNum); };

    $.fn.dataTableExt.oSort['title-date-asc']  = function (a,b) { return sortSpecial(a, b, true, convertDate); };

    $.fn.dataTableExt.oSort['title-date-desc']  = function (a,b) { return sortSpecial(a, b, false, convertDate); };

    return {
        HQReportDataTables: function (options) { return new HQReportDataTables(options); },
    };
});
