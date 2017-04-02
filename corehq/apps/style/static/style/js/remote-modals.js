$(function() {
    _.each($(".remote-modal"), function(modal) {
        $(modal).on("show show.bs.modal", function() {
            $(this).find(".fetched-data").load($(this).data("url"));
        });
    });
});
