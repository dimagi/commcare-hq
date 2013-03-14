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

    // disable-on-submit is a class for form submit buttons so they're automatically disabled when the form is submitted
    $(document).on('submit', 'form', function(ev) {
        var form = $(ev.target);
        form.find('.disable-on-submit').prop('disabled',true).addClass('disabled');
    });

    $(document).on('click', '.notification-close-btn', function() {
        var note_id = $(this).data('note-id');
        var post_url = $(this).data('url');
        $.post(post_url, {note_id: note_id});
        $(this).parents('.alert').hide(150);
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
