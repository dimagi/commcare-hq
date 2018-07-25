/*
 * Main module for non-report ilsgateway pages
 */
hqDefine("ilsgateway/js/main", function() {
    // Pending Recalculations page
    var $recalculations = $('#recalculations');
    if ($recalculations.length) {
        $recalculations.dataTable();
    }
});
