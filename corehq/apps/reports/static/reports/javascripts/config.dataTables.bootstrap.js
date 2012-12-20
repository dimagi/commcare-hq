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
    self.customSort = options.customSort;
    self.ajaxParams = options.ajaxParams || new Object();
    self.ajaxSource = options.ajaxSource;
    self.loadingText = options.loadingText || "Loading...";
    self.emptyText = options.emptyText || "No data available to display. Please try changing your filters.";
    self.fixColumns = !!(options.fixColumns);
    self.fixColsNumLeft = options.fixColsNumLeft || 1;
    self.fixColsWidth = options.fixColsWidth || 100;
    self.datatable = null;


    this.render = function () {

        $('[data-datatable-highlight-closest]').each(function () {
           $(this).closest($(this).attr('data-datatable-highlight-closest')).addClass('active');
        });
        $('[data-datatable-tooltip]').each(function () {
            $(this).tooltip({
                placement: $(this).attr('data-datatable-tooltip'),
                title: $(this).attr('data-datatable-tooltip-text')
            });
        });

        var dataTablesDom = "frt<'row-fluid dataTables_control'<'span5'il><'span7'p>>";
        $(self.dataTableElem).each(function(){
            var params = {
                sDom: dataTablesDom,
                sPaginationType: self.paginationType,
                iDisplayLength: self.defaultRows,
                bAutoWidth: self.autoWidth,
                sScrollX: "100%"
            };

            if(self.ajaxSource) {
                params.bServerSide = true;
                params.bProcessing = true;
                params.sAjaxSource = self.ajaxSource;
                params.bFilter = $(this).data('filter') || false;
                params.fnServerParams = function ( aoData ) {
                    for (var p in self.ajaxParams) {
                        var currentParam = self.ajaxParams[p];
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
jQuery.fn.dataTableExt.oSort['title-numeric-asc']  = function(a,b) {
    var x = a.match(/title="*(-?[0-9]+)/);
    var y = b.match(/title="*(-?[0-9]+)/);

    if (x === null && y === null) return 0;
    if (x === null) return -1;
    if (y === null) return 1;

    x = parseFloat(x[1]);
    y = parseFloat(y[1]);
    return ((x < y) ? -1 : ((x > y) ?  1 : 0));
};
jQuery.fn.dataTableExt.oSort['title-numeric-desc'] = function(a,b) {
    var x = a.match(/title="*(-?[0-9]+)/);
    var y = b.match(/title="*(-?[0-9]+)/);

    if (x === null && y === null) return 0;
    if (x === null) return 1;
    if (y === null) return -1;

    x = parseFloat(x[1]);
    y = parseFloat(y[1]);
    return ((x < y) ?  1 : ((x > y) ? -1 : 0));
};
