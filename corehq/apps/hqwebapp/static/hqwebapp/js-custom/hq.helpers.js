$(function() {
    // trick to give a select menu an initial value
    $('select[data-value]').each(function () {
        var val = $(this).attr('data-value');
        if (val) {
            $(this).find('option').removeAttr('selected');
            $(this).find('option[value="' + val + '"]').attr('selected', 'true');
        }
    });
});