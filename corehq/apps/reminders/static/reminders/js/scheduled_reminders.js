/* globals moment */
hqDefine("reminders/js/scheduled_reminders", function() {
    $(function () {
        var reminders = _.map(hqImport("hqwebapp/js/initial_page_data").get("reminder_data"), function(data) {
                var next_fire = moment.utc(data.next_fire);
                return {
                    nickname: data.handler_name,
                    date: next_fire.format("YYYY-MM-DD"),
                    time: next_fire.format("h:mm a"),
                    case_name: data.case_name,
                    case_url: data.case_id ? hqImport("hqwebapp/js/urllib").reverse("case_details", data.case_id) : "",
                    recipient_desc: data.recipient_desc,
                    recipient_type: data.recipient_type,
                };
            }),
            i,
            reminder;
        reminders.push(null);
        for (i = 0; i < reminders.length; i += 1) {
            reminder = reminders[i];
            if (reminder) {
                var recipient_text;
                if (_.contains(["USER", "OWNER", "CASE", "PARENT_CASE", "SUBCASE"], reminder.recipient_type)) {
                    var case_url = '<a href="' + reminder.case_url + '">' + reminder.case_name + '</a>';
                    if (reminder.recipient_type === "CASE") {
                        recipient_text = case_url;
                    } else {
                        recipient_text = reminder.recipient_desc + " for " + case_url;
                    }
                } else {
                    recipient_text = reminder.recipient_desc;
                }
                $('.calendar [data-date="' + reminder.date + '"]').append(
                    $('<li/>').append(
                        $('<span/>').text(reminder.time).addClass('time-header')
                    ).append(
                        $('<span/>').html(
                            " <b>" + reminder.nickname + "</b> to " + recipient_text
                        )
                    )
                );
            }
        }
        $('.calendar-first').each(function () {
            var i = 0, className = 'calendar-first-week', day = $(this);
            for (i = 0; i < 7; i += 1) {
                day.addClass(className);
                if (day.next().length) {
                    day = day.next();
                } else if (day.parent().next().find('> td')) {
                    day = day.parent().next().find('> td').first();
                }
            }
        });
    });
});
