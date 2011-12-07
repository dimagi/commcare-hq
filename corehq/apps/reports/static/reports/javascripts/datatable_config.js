// datatable configuration.
function start_datatables(elem){
    if(!elem){
        elem = document;
    }
    $('.datatable', elem).each(function(){
        var params = {
            "bJQueryUI": true
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
                "bFilter": filter
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