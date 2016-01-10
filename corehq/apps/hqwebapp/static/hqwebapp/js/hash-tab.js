$(function(){
    // http://stackoverflow.com/questions/12131273/twitter-bootstrap-tabs-url-doesnt-change#answer-12138756
    // todo: consider adding this to hq.helpers
    var hash = window.location.hash;
    hash && $('ul.nav a[href="' + hash + '"]').tab('show');

    $('.nav-tabs a[data-toggle="hash-tab"]').click(function (e) {
        e.preventDefault();
        $(this).tab('show');
        var scrollmem = $('body').scrollTop();
        window.location.hash = this.hash;
        $('html,body').scrollTop(scrollmem);
    });

    $('.nav-tabs a[data-toggle="tab"]').on('shown.bs.tab', function (e) {
        $(window).trigger('resize');
    });
});
