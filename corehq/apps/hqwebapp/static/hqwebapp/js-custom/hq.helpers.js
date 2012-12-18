$(function() {
    // trick to give a select menu an initial value
    $('select[data-value]').each(function () {
        var val = $(this).attr('data-value');
        if (val) {
            $(this).find('option').removeAttr('selected');
            $(this).find('option[value="' + val + '"]').attr('selected', 'true');
        }
    });

    var clearAnnouncement = function (announcementID) {
        $.ajax({
            url: '/announcements/clear/' + announcementID
        });
    };

    $('.page-level-alert').bind('closed', function () {
        var announcement_id = $('.page-level-alert').find('.announcement-control').data('announcementid');
        if (announcement_id) {
            clearAnnouncement(announcement_id);
        }
    });
});

$.fn.hqHelp = function () {
    var self = this;
    self.each(function(i) {
        var $helpElem = $($(self).get(i));
        $helpElem.find('i').popover();
        $helpElem.click(function () {
            if ($helpElem.find('i').attr('data-trigger') != 'hover') {
                $(this).toggleClass('on');
            }
            if ($(this).hasClass('no-click')) {
                return false;
            }
        })
    });
};
