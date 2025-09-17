import $ from 'jquery';
import initialPageData from 'hqwebapp/js/initial_page_data';

import 'datatables.net/js/jquery.dataTables';
import 'datatables.net-fixedcolumns/js/dataTables.fixedColumns';
import 'datatables.net-fixedcolumns-bs5/js/fixedColumns.bootstrap5';

$(function () {
    $('#example-datatable').dataTable({
        // This defines the layout of the datatable and is important for getting everything to look standard
        dom: "frt<'d-flex mb-1'<'p-2 ps-3'i><'p-2 ps-0'l><'ms-auto p-2 pe-3'p>>",
        // hides the search bar, since we often use datatables with reports that have their own set of advanced filters beyond simple search
        filter: false,
        language: {
            // in the past we used custom javascript to find the length menu text and update it. please avoid this. opt for using the language options
            lengthMenu: "_MENU_ per page",
        },
        scrollX: "100%",
        fixedColumns: {
            left: 1,
        },
        columnDefs: [
            { width: 80, targets: 0 },
        ],
        // this just pre-fills the datatables with a large set of data. server-side pagination can be enabled with the serverSide option as well as the "processing..." label. see datatable's docs for usage details
        ajax: {
            url: initialPageData.reverse("styleguide_datatables_data"),
            type: "POST",
        },
    });
});
