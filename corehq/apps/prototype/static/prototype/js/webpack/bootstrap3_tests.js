hqDefine("prototype/js/example/bootstrap3_tests_webpack", [
    'hqwebapp/js/initial_page_data',
    'commcarehq_b3',
    'jquery',
    'knockout',
    'ko.mapping',
    'underscore',
], function (initialPageData) {
    console.log('this is a bootstrap 3 webpack bundle');
    console.log(initialPageData.get('test_initial_b3'));
});