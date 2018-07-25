/*
 * Main module for non-report ilsgateway pages
 */
hqDefine("ilsgateway/js/main", function() {
    $(function() {
        // Supervision Docs page
        $('.delete').click(function() {
            $(this).parent().find('.modal').modal();
        });

        // Pending Recalculations page
        var $recalculations = $('#recalculations');
        if ($recalculations.length) {
            $recalculations.dataTable();
        }
    });
});
