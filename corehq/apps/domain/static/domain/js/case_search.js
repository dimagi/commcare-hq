hqDefine('domain/js/case_search', function() {
     (function () {
         var CaseSearchConfig = hqImport('domain/js/case-search-config').CaseSearchConfig;
         var viewModel = new CaseSearchConfig({
             values: {{ values|JSON }},
             caseTypes: {{ case_types|JSON }},
         });
         $('#case-search-config').koApplyBindings(viewModel);
         $('#case-search-config').on('change', viewModel.change).on('click', ':button', viewModel.change);
     }());
});
