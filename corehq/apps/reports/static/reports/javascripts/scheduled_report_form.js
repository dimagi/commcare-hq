function add_options_to_select($select, opt_list, selected_val) {
    for (var i = 0; i < opt_list.length; i++) {
        var $opt = $('<option />').val(opt_list[i][0]).text(opt_list[i][1]);
        if (opt_list[i][0] === selected_val) {
            $opt.attr("selected", "true");
        }
        $select.append($opt);
    }
    return $select;
}

function update_day_input(weekly_options, monthly_options, day_value) {
    var $interval = $interval || $('[name="interval"]');
    $('#div_id_day').remove();
    if ($interval.val() !== 'daily') {
        var opts = ($interval.val() === 'weekly' || $interval.val() === 'n_weeks'
            ? weekly_options : monthly_options);
        var $day_select = $('<select id="id_day" class="select" name="day" />');
        $day_select = add_options_to_select($day_select, opts, day_value);
        var $day_control_group = $('<div id="div_id_day" class="control-group" />')
                .append($('<label for="id_day" class="control-label requiredField">Day<span class="asteriskField">*</span></label>'))
                .append($('<div class="controls" />').append($day_select));
        $interval.parents('.control-group').after($day_control_group);
    }
}

var ScheduledReportFormHelper = function(options) {
    var self = this;
    self.weekly_options = options.weekly_options;
    self.monthly_options = options.monthly_options;
    self.day_value = options.day_value;

    self.init = function() {
        $(function() {
            update_day_input(self.weekly_options, self.monthly_options, self.day_value);
            $('[name="interval"]').change(function() {
                update_day_input(self.weekly_options, self.monthly_options);
            })
        });
    };
};
