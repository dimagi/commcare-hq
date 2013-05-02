$(function () {
    $(".more-sortable-button").click(function() {
        var e = $(this);
        var sortable = e.data('sortable');
        $('.sortable-' + sortable).show();
        e.hide();
        return false;
    });

    $(".facet-checkbox").click(function() {
        window.location = $(this).parent().attr('href');
    });
});