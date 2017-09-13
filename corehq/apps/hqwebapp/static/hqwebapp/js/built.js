/* globals define */
hqGlobal("hqwebapp/js/built", [
    "hqwebapp/js/alert_user",
    "hqwebapp/js/initial_page_data",
    "hqwebapp/js/main",
    "hqwebapp/js/hq.helpers",
], function(
    alertUser,
    initialPageData,
    main
){
    return {
        alertUser: alertUser,
        initialPageData: initialPageData,
        main: main
    };
});
