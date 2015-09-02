// datatable configuration.

function HQReportDataTables(options) {
    var self = this;
    self.dataTableElem = options.dataTableElem || '.datatable';
    self.paginationType = options.paginationType || 'bootstrap';
    self.defaultRows = options.defaultRows || 10;
    self.startAtRowNum = options.startAtRowNum || 0;
    self.showAllRowsOption = options.showAllRowsOption || false;
    self.aoColumns = options.aoColumns;
    self.autoWidth = (options.autoWidth != undefined) ? options.autoWidth : true;
    self.defaultSort = (options.defaultSort != undefined) ? options.defaultSort : true;
    self.customSort = options.customSort;
    self.ajaxParams = options.ajaxParams || new Object();
    self.ajaxSource = options.ajaxSource;
    self.loadingText = options.loadingText || "Loading <img src='/static/hqwebapp/img/ajax-loader.gif' alt='loading indicator' />";
    self.emptyText = options.emptyText || "No data available to display. Please try changing your filters.";
    self.errorText = options.errorText || "<span class='label label-important'>Sorry!</span> There was an error with your query, it has been logged, please try another query.";
    self.badRequestErrorText = options.badRequestErrorText || options.errorText || "<span class='label label-important'>Sorry!</span> Your search query is invalid, please adjust the formatting and try again.";
    self.fixColumns = !!(options.fixColumns);
    self.fixColsNumLeft = options.fixColsNumLeft || 1;
    self.fixColsWidth = options.fixColsWidth || 100;
    self.show_pagination = (options.show_pagination === undefined) ? true : options.bPaginate;
    // a list of functions to call back to after ajax.
    // see user configurable charts for an example usage
    self.extraCallbacks = options.extraCallbacks;
    self.datatable = null;
    self.rendered = false;

    this.render_footer_row = (function() {
        var $dataTableElem = $(self.dataTableElem);
        return function(id, row) {
            if ($dataTableElem.find('tfoot').length === 0) {
                var $row = $dataTableElem.find('#' + id);
                if ($row.length == 0) {
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

    this.render = function () {
        if (self.rendered) {
            $(self.dataTableElem).each(function () {
                $(this).dataTable().fnReloadAjax();
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
                    title: $(this).attr('data-datatable-tooltip-text')
                });
            });
        }
        applyBootstrapMagic();

        var dataTablesDom = "frt<'row-fluid dataTables_control'<'span5'il><'span7'p>>";
        $(self.dataTableElem).each(function(){
            var params = {
                sDom: dataTablesDom,
                bPaginate: self.show_pagination,
                sPaginationType: self.paginationType,
                iDisplayLength: self.defaultRows,
                bAutoWidth: self.autoWidth,
                sScrollX: "100%",
                bSort: self.defaultSort
            };

            if(self.ajaxSource) {
                params.bServerSide = true;
                params.bProcessing = true;
                params.sAjaxSource = self.ajaxSource;
                params.bFilter = $(this).data('filter') || false;
                params.fnServerParams = function ( aoData ) {
                    var ajaxParams = $.isFunction(self.ajaxParams) ? self.ajaxParams() : self.ajaxParams;
                    for (var p in ajaxParams) {
                        if (ajaxParams.hasOwnProperty(p)) {
                            var currentParam = ajaxParams[p];
                            if(_.isObject(currentParam.value)) {
                                for (var j=0; j < currentParam.value.length; j++) {
                                    aoData.push({
                                        name: currentParam.name,
                                        value: currentParam.value[j]
                                    });
                                }
                            } else {
                                aoData.push(currentParam);
                            }
                        }
                    }
                };
                params.fnServerData = function ( sSource, aoData, fnCallback, oSettings ) {
                    var custom_callback = function(data) {
                        var result = fnCallback(data); // this must be called first because datatables clears the tfoot of the table
                        var i;
                        if ('total_row' in data) {
                            self.render_footer_row('ajax_total_row', data['total_row']);
                        }
                        if ('statistics_rows' in data) {
                            for (i = 0; i < data.statistics_rows.length; i++){
                               self.render_footer_row('ajax_stat_row-' + i, data.statistics_rows[i]);
                            }
                        }
                        applyBootstrapMagic();
                        if ('context' in data){
                            load(data['context'], ICON_PATH);
                        }
                        if (self.extraCallbacks) {
                            for (i = 0; i < self.extraCallbacks.length; i++) {
                                self.extraCallbacks[i](data);
                            }
                        }
                        return result
                    };

                    oSettings.jqXHR = $.ajax( {
                        "url": sSource,
                        "data": aoData,
                        "success": custom_callback,
                        "error": function(data) {
                            $(".dataTables_processing").hide();
                            if (data.status === 400) {
                                $(".dataTables_empty").html(self.badRequestErrorText);
                            } else {
                                $(".dataTables_empty").html(self.errorText);                                
                            }
                            $(".dataTables_empty").show();
                        }
                    } );
                };
            }
            params.oLanguage = {
                sProcessing: self.loadingText,
                sLoadingRecords: self.loadingText,
                sZeroRecords: self.emptyText
            };

            params.fnDrawCallback = function (a,b,c) {
                /* be able to set fnDrawCallback from outside here later */
                if (self.fnDrawCallback) {
                    self.fnDrawCallback(a,b,c);
                }
            };

            if(self.aoColumns)
                params.aoColumns = self.aoColumns;

            var datatable = $(this).dataTable(params);
            if (!self.datatable)
                self.datatable = datatable;
            if(self.customSort) {
                datatable.fnSort( self.customSort );
            }
            if(self.fixColumns)
                new FixedColumns( datatable, {
                    iLeftColumns: self.fixColsNumLeft,
                    iLeftWidth: self.fixColsWidth
                } );
            $(window).on('resize', function () {
                datatable.fnAdjustColumnSizing();
            } );


            var $dataTablesFilter = $(".dataTables_filter");
            if($dataTablesFilter && $("#extra-filter-info")) {
                if($dataTablesFilter.length > 1) {
                    $($dataTablesFilter.first()).remove();
                    $dataTablesFilter = $($dataTablesFilter.last());
                }
                $("#extra-filter-info").html($dataTablesFilter);
                $dataTablesFilter.addClass("form-search");
                var $inputField = $dataTablesFilter.find("input"),
                    $inputLabel = $dataTablesFilter.find("label");

                $dataTablesFilter.append($inputField);
                $inputField.attr("id", "dataTables-filter-box");
                $inputField.addClass("search-query").addClass("input-medium");
                $inputField.attr("placeholder", "Search...");

                $inputLabel.attr("for", "dataTables-filter-box");
                $inputLabel.html($('<i />').addClass("icon-search"));
            }

            var $dataTablesLength = $(".dataTables_length"),
                $dataTablesInfo = $(".dataTables_info");
            if($dataTablesLength && $dataTablesInfo) {
                var $selectField = $dataTablesLength.find("select"),
                    $selectLabel = $dataTablesLength.find("label");

                $dataTablesLength.append($selectField);
                $selectLabel.remove();
                $selectField.children().append(" per page");
                if (self.showAllRowsOption)
                    $selectField.append($('<option value="-1" />').text("All Rows"));
                $selectField.addClass("input-medium");
                $selectField.on("change", function(){
                    var selected_value = $selectField.find('option:selected').val();
                    window.analytics.usage("Reports", "Changed number of items shown", selected_value);
                });
            }
            $(".dataTables_length select").change(function () {
                $(self.dataTableElem).trigger('hqreport.tabular.lengthChange', $(this).val());
            });
        });
    };
}

$.extend( $.fn.dataTableExt.oStdClasses, {
    "sSortAsc": "header headerSortDown",
    "sSortDesc": "header headerSortUp",
    "sSortable": "header"
} );

// For sorting rows

function sortSpecial(a, b, asc, convert) {
    var x = convert(a);
    var y = convert(b);

    // sort nulls at end regardless of current sort direction
    if (x === null && y === null) return 0;
    if (x === null) return 1;
    if (y === null) return -1;

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
    return new Date(m[1]);
}

jQuery.fn.dataTableExt.oSort['title-numeric-asc'] = function(a, b) { return sortSpecial(a, b, true, convertNum); };

jQuery.fn.dataTableExt.oSort['title-numeric-desc'] = function(a, b) { return sortSpecial(a, b, false, convertNum); };

jQuery.fn.dataTableExt.oSort['title-date-asc']  = function(a,b) { return sortSpecial(a, b, true, convertDate); };

jQuery.fn.dataTableExt.oSort['title-date-desc']  = function(a,b) { return sortSpecial(a, b, false, convertDate); };
