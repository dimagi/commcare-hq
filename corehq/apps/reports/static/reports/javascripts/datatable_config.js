// datatable configuration.
function start_datatables(elem){
    if(!elem){
        elem = document;
    }
    $('.datatable', elem).each(function(){
        var params = {
            "bJQueryUI": true,
            "sPaginationType": "full_numbers"
        },
            sAjaxSource = $(this).data('source'),
            filter = $(this).data('filter') || false,
            aoColumns = [],
            $columns = $(this).find('tr').first().find('th'),
            i;

        if(sAjaxSource) {
            params = {
                "bJQueryUI": true,
                "bServerSide": true,
                "sAjaxSource": sAjaxSource,
                "bSort": false,
                "bFilter": filter,
                "sPaginationType": "full_numbers",
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
    });
    $('.datatable').parent().find('.fg-toolbar').removeClass('ui-corner-tr ui-corner-tl');
}
$(document).ready(function() {
    start_datatables();
});