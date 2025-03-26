import $ from 'jquery';

import 'datatables.net/js/jquery.dataTables';
import 'datatables.net-fixedcolumns/js/dataTables.fixedColumns';
import 'datatables.net-fixedcolumns-bs5/js/fixedColumns.bootstrap5';

import _ from 'underscore';
import googleAnalytics from 'analytix/js/google';
import {Tooltip} from 'bootstrap5';


var HQReportDataTables = function (options) {
    var self = {};
    self.dataTableElem = options.dataTableElem || '.table-hq-report';
    self.forcePageSize = options.forcePageSize || false;
    self.defaultRows = options.defaultRows || 10;
    self.showAllRowsOption = options.showAllRowsOption || false;
    self.columns = options.aoColumns;  // todo eventually rename aoColumns outside of file
    self.autoWidth = (options.autoWidth !== undefined) ? options.autoWidth : true;
    self.defaultSort = (options.defaultSort !== undefined) ? options.defaultSort : true;
    self.customSort = options.customSort || null;
    self.ajaxParams = options.ajaxParams || {};
    self.ajaxSource = options.ajaxSource;
    self.loadingText = options.loadingText || gettext("Loading");
    self.emptyText = options.emptyText || gettext("No data available to display. " +
                                                  "Please try changing your filters.");
    self.errorText = options.errorText || "<span class='badge text-bg-danger'>" + gettext("Sorry!") + "</span> " +
                     gettext("There was an error with your query, it has been logged, please try another query.");
    self.badRequestErrorText = options.badRequestErrorText || options.errorText ||
                               "<span class='badge text-bg-danger'>" + gettext("Sorry!") + "</span> " +
                               gettext("Your search query is invalid, please adjust the formatting and try again.");
    self.fixColumns = !!(options.fixColumns);
    self.fixColsNumLeft = options.fixColsNumLeft || 1;
    self.fixColsWidth = options.fixColsWidth || 100;
    self.show_pagination = (options.show_pagination === undefined) ? true : options.bPaginate;
    self.order = options.aaSorting || null; // todo eventually rename aaSorting outside of file
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
                new Tooltip($(this).get(0), {
                    placement: $(this).attr('data-datatable-tooltip'),
                    title: $(this).attr('data-datatable-tooltip-text'),
                });
            });
        }
        applyBootstrapMagic();

        var dataTablesDom = "frt<'d-flex mb-1'<'p-2 ps-3'i><'p-2 ps-0'l><'ms-auto p-2 pe-3'p>>";
        $(self.dataTableElem).each(function () {
            const params = {
                dom: dataTablesDom,
                filter: false,
                paging: self.show_pagination,
                pageLength: self.defaultRows,
                autoWidth: self.autoWidth,
                scrollX: "100%",
                ordering: self.defaultSort,
                searching: self.includeFilter,
            };
            if (self.order !== null || self.customSort !== null) {
                params.order = self.order || self.customSort;
            }

            if (self.ajaxSource) {
                params.serverSide = true;
                params.processing = true;
                params.ajax = {
                    url: self.ajaxSource,
                    method: 'POST',
                    data: function (data) {
                        // modify the query sent to server to include HQ Filters
                        self.addHqFiltersToServerSideQuery(data);
                    },
                    error: function (jqXHR, statusText, errorThrown) {
                        $(".dataTables_processing").hide();
                        if (jqXHR.status === 400) {
                            let errorMessage = self.badRequestErrorText;
                            if (jqXHR.responseText) {
                                errorMessage = "<p><span class='badge text-bg-danger'>" + gettext("Sorry!") + "</span> " + jqXHR.responseText + "</p>";
                            }
                            $(".dataTables_empty").html(errorMessage);
                        } else {
                            $(".dataTables_empty").html(self.errorText);
                        }
                        $(".dataTables_empty").show();
                        if (self.errorCallbacks) {
                            for (let i = 0; i < self.errorCallbacks.length; i++) {
                                self.errorCallbacks[i](jqXHR, statusText, errorThrown);
                            }
                        }
                    },
                };
                params.searching = $(this).data('filter') || false;
                self.addHqFiltersToServerSideQuery = function (data) {
                    let ajaxParams = $.isFunction(self.ajaxParams) ? self.ajaxParams() : self.ajaxParams;
                    data.hq = {};
                    for (let p in ajaxParams) {
                        if (_.has(ajaxParams, p)) {
                            let param = ajaxParams[p];
                            data.hq[param.name] = _.isArray(param.value) ? _.uniq(param.value) : param.value;
                        }
                    }
                    return data;
                };

                params.footerCallback = function (row, data, start, end, display) {
                    if ('total_row' in data) {
                        self.render_footer_row('ajax_total_row', data['total_row']);
                    }
                    if ('statistics_rows' in data) {
                        for (let i = 0; i < data.statistics_rows.length; i++) {
                            self.render_footer_row('ajax_stat_row-' + i, data.statistics_rows[i]);
                        }
                    }
                };

                params.drawCallback = function () {
                    let api = this.api(),
                        data = api.ajax.json();

                    if (data.warning) {
                        throw new Error(data.warning);
                    }
                    applyBootstrapMagic();
                    if ('context' in data) {
                        let iconPath = data['icon_path'] || $(".base-maps-data").data("icon_path");
                        import("reports/js/bootstrap5/maps_utils").then(function (mapsUtils) {
                            mapsUtils.load(data['context'], iconPath);
                        });
                    }
                    if (self.successCallbacks) {
                        for (let i = 0; i < self.successCallbacks.length; i++) {
                            self.successCallbacks[i](data);
                        }
                    }
                };
            }
            params.language = {
                lengthMenu: gettext("_MENU_ per page"),
                processing: self.loadingText,
                loadingRecords: self.loadingText,
                zeroRecords: self.emptyText,
            };

            if (self.columns) {
                params.columns = self.columns;
            }

            if (self.forcePageSize) {
                // limit the page size option to just the default size
                params.lengthMenu = [self.defaultRows];
            }

            if (self.fixColumns) {
                new $.fn.dataTable.FixedColumns(datatable, {
                    iLeftColumns: self.fixColsNumLeft,
                    iLeftWidth: self.fixColsWidth,
                });
                params.fixedColumns = {
                    left: self.fixColsNumLeft,
                    width: self.fixColsWidth,
                };
            }
            let datatable = $(this).dataTable(params);
            if (!self.datatable) {
                self.datatable = datatable;
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

            let $dataTablesLength = $(self.dataTableElem).parents('.dataTables_wrapper').find(".dataTables_length");
            if ($dataTablesLength) {
                let $selectField = $dataTablesLength.find("select");
                if (self.showAllRowsOption) {
                    $selectField.append($('<option value="-1" />').text(gettext("All Rows")));
                }
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

export default {
    HQReportDataTables: function (options) {
        return new HQReportDataTables(options);
    },
};
