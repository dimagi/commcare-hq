function shiftDates(days) {
    var start, end;
    start = new Date($("#startdate").val());
    start.setDate(start.getDate() + days);
    end = new Date($("#enddate").val());
    end.setDate(end.getDate() + days);
    $("#startdate").datepicker('setDate', start);
    $("#enddate").datepicker('setDate', end);
    $("#paramSelectorForm").submit();
};

$(function() {
    $('.date-picker').datepicker({
        changeMonth: true,
        changeYear: true,
        showButtonPanel: true,
        dateFormat: 'yy-mm-dd',
        numberOfMonths: 2
    });
    $('#startdate').change(function(){
        $("#enddate").datepicker('option', 'minDate', $('#startdate').val());
    }).trigger('change');
    $("#previous_date").click(function(e){
        e.preventDefault();
        shiftDates(-7);
    });
    $("#next_date").click(function(e){
        e.preventDefault();
        shiftDates(7);
    });
});
