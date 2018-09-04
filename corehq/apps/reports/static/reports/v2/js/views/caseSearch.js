/**
 * todo add docstring
 */

hqDefine('reports/v2/js/views/caseSearch', [
  'jquery',
  'knockout',
  'lodash',
  'reports/v2/js/context',
  'datatables',
  'datatables.scroller',
  'datatables.colReorder',
], function (
  $,
  ko,
  _,
  Context
) {
  'use strict';
  var view = {};

  view.config = Context.getReportConfig();

  $(function () {
    view.config.init();

    console.log(view.config.endpoint.datatables.getUrl());

    // view.config.endpoint.datatables.post({
    //   init: "hi",
    // }).done(function ( data ) {
    //   console.log('post done');
    //   console.log(data);
    // });
    //

    $('#report-datatable').dataTable({
      colReorder: true,
      serverSide: true,
      ordering: true,
      searching: false,
      ajax: {
        url: view.config.endpoint.datatables.getUrl(),
        type: "POST",
        data: function (tableData) {
          tableData.foo = "bar";
        }
      },
      scrollY: 500,
      scroller: {
          loadingIndicator: true
      },
      stateSave: true,
      deferRender: true,
      columns: [
        { data: "@case_type", defaultContent: "--", title: "@case_type" },
        { data: "case_name", defaultContent: "--" , title: "case_name"},
        { data: "@@__add_column", defaultContent: "", title: '<a href="#" class="btn">add column</a>'}
      ]
    });

  });


  return view;
});
