// datatable configuration.
function start_datatables(elem){
    if(!elem){
        elem = document;
    }
    var dataTablesDom = "frt<'row-fluid dataTables_control'<'span5'il><'span7'p>>";
    $('.datatable', elem).each(function(){
        var params = {
            "sDom": dataTablesDom,
            "sPaginationType": "bootstrap"
        },
            sAjaxSource = $(this).data('source'),
            filter = $(this).data('filter') || false,
            aoColumns = [],
            $columns = $(this).find('tr').first().find('th'),
            i;

        if(sAjaxSource) {
            params = {
                "sDom": dataTablesDom,
                "sPaginationType": "bootstrap",
                "bServerSide": true,
                "sAjaxSource": sAjaxSource,
                "bSort": false,
                "bFilter": filter,
                "fnServerParams": function ( aoData ) {
                    aoData.push({ "name" : 'individual', "value": $(this).data('individual')});
                    aoData.push({ "name" : 'group', "value": $(this).data('group')});
                    aoData.push({ "name" : 'case_type', "value": $(this).data('casetype')});
                    ufilter = $(this).data('ufilter');
                    if (ufilter) {
                        for (var i=0;i<ufilter.length;i++) {
                            aoData.push({ "name" : 'ufilter', "value": ufilter[i]});
                        }
                    }

                }
            };
        }
        for (i = 0; i < $columns.length; i += 1) {
            var sortType = $($columns[i]).data('sort');
            if (sortType) {
                aoColumns.push({sType: sortType});
            } else {
                aoColumns.push(null);
            }
        }
        params.aoColumns = aoColumns;
        $(this).dataTable(params);

        var $dataTablesFilter = $(".dataTables_filter");
        if($dataTablesFilter) {
            $("#extra-filter-info").append($dataTablesFilter);
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
            $selectField.addClass("input-medium");
        }

    });
    //$('.datatable').parent().find('.fg-toolbar').removeClass('ui-corner-tr ui-corner-tl');

}
$.extend( $.fn.dataTableExt.oStdClasses, {
    "sSortAsc": "header headerSortDown",
    "sSortDesc": "header headerSortUp",
    "sSortable": "header"
} );

// For sorting rows
jQuery.fn.dataTableExt.oSort['title-numeric-asc']  = function(a,b) {
    var x = a.match(/title="*(-?[0-9]+)/)[1];
    var y = b.match(/title="*(-?[0-9]+)/)[1];
    x = parseFloat( x );
    y = parseFloat( y );
    return ((x < y) ? -1 : ((x > y) ?  1 : 0));
};
jQuery.fn.dataTableExt.oSort['title-numeric-desc'] = function(a,b) {
    var x = a.match(/title="*(-?[0-9]+)/)[1];
    var y = b.match(/title="*(-?[0-9]+)/)[1];
    x = parseFloat( x );
    y = parseFloat( y );
    return ((x < y) ?  1 : ((x > y) ? -1 : 0));
};

$(document).ready(function() {
    start_datatables();
});
