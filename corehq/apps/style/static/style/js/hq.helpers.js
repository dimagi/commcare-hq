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
        form.find('.disable-on-submit').disableButton();
        form.find('.disable-on-submit-no-spinner').disableButtonNoSpinner();
    });
    $(document).on('submit', 'form.disable-on-submit', function (ev) {
        $(ev.target).find('[type="submit"]').disableButton();
    });
    $(document).on('click', '.add-spinner-on-click', function(ev) {
        $(ev.target).addSpinnerToButton();
    });

    $(document).on('click', '.notification-close-btn', function() {
        var note_id = $(this).data('note-id');
        var post_url = $(this).data('url');
        $.post(post_url, {note_id: note_id});
        $(this).parents('.alert').hide(150);
    });
});

var oldHide = $.fn.popover.Constructor.prototype.hide;

$.fn.popover.Constructor.prototype.hide = function() {
    if (this.options.trigger === "hover" && this.tip().is(":hover")) {
        var that = this;
        setTimeout(function() {
            return that.hide.call(that, arguments);
        }, that.options.delay.hide);
        return;
    }
    oldHide.call(this, arguments);
};

$.fn.hqHelp = function () {
    var self = this;
    self.each(function(i) {
        var $helpElem = $($(self).get(i));
        $helpElem.find('i').popover({
            html: true,
            content: function() {
                return $('#popover_content_wrapper').html();
            }
        })
    });
};

$.showMessage = function (message, level) {
    $notice = $('<div />').addClass("alert fade in alert-block alert-full page-level-alert")
        .addClass("alert-" + level);
    var $closeIcon = $('<a />').addClass("close").attr("data-dismiss", "alert");
    $closeIcon.attr("href", "#").html("&times;");
    $notice.append($closeIcon);
    $notice.append(message);
    $(".hq-page-header-container").prepend($notice);
};


$.fn.addSpinnerToButton = function () {
    $(this).prepend('<i class="icon-refresh icon-spin"></i> ');
};


$.fn.removeSpinnerFromButton = function () {
    $(this).find('i').remove();
};


$.fn.disableButtonNoSpinner = function () {
    $(this).attr('disabled', 'disabled')
           .addClass('disabled');
};


$.fn.disableButton = function () {
    $(this).disableButtonNoSpinner();
    $(this).addSpinnerToButton();
};


$.fn.enableButton = function () {
    $(this).removeSpinnerFromButton();
    $(this).removeClass('disabled')
           .removeAttr('disabled');
};

var SaveButton = {
    /*
        options: {
            save: "Function to call when the user clicks Save",
            unsavedMessage: "Message to display when there are unsaved changes and the user leaves the page"
        }
    */
    init: function (options) {
        var button = {
            disabled: false,
            $save: $('<span/>').text(SaveButton.message.SAVE).click(function () {
                button.fire('save');
            }).addClass('btn btn-success'),
            $retry: $('<span/>').text(SaveButton.message.RETRY).click(function () {
                button.fire('save');
            }).addClass('btn btn-success'),
            $saving: $('<span/>').text(SaveButton.message.SAVING).prepend('<i class="fa fa-refresh fa-spin"></i> ').addClass('btn disabled'),
            $saved: $('<span/>').text(SaveButton.message.SAVED).addClass('btn disabled'),
            ui: $('<div/>').addClass('pull-right'),
            setStateWhenReady: function (state) {
                if (this.state === 'saving') {
                    this.nextState = state;
                } else {
                    this.setState(state);
                }
            },
            setState: function (state) {
                if (this.state === state) {
                    return;
                }
                this.state = state;
                this.$save.detach();
                this.$saving.detach();
                this.$saved.detach();
                this.$retry.detach();
                if (state === 'save') {
                    this.ui.append(this.$save);
                } else if (state === 'saving') {
                    this.ui.append(this.$saving);
                } else if (state === 'saved') {
                    this.ui.append(this.$saved);
                } else if (state === 'retry') {
                    this.ui.append(this.$retry);
                }
                this.fire('state:change');
            },
            ajaxOptions: function (options) {
                var options = options || {},
                    beforeSend = options.beforeSend || function () {},
                    success = options.success || function () {},
                    error = options.error || function () {},
                    that = this;
                options.beforeSend = function () {
                    that.setState('saving');
                    that.nextState = 'saved';
                    beforeSend.apply(this, arguments);
                };
                options.success = function (data) {
                    that.setState(that.nextState);
                    success.apply(this, arguments);
                };
                options.error = function (data) {
                    that.nextState = null;
                    that.setState('retry');
                    responseText = data.responseText || '';
                    alert(SaveButton.message.ERROR_SAVING + '\n' +  data.responseText);
                    error.apply(this, arguments);
                };
                return options;
            },
            ajax: function (options) {
                var jqXHR = $.ajax(button.ajaxOptions(options));
                if (!jqXHR) {
                    // request was aborted
                    this.setState('save');
                }
            }
        };
        eventize(button);
        button.setState('saved');
        button.on('change', function () {
            this.setStateWhenReady('save');
        });
        button.on('disable', function () {
            this.disabled = true;
            this.$save.addClass('disabled');
            this.$saving.addClass('disabled');
            this.$retry.addClass('disabled');
        });
        button.on('enable', function () {
            this.disabled = false;
            this.$save.removeClass('disabled');
            this.$saving.removeClass('disabled');
            this.$retry.removeClass('disabled');
        });
        button.on('save', function () {
            if (button.disabled){
                return;
            } else if (options.save) {
                options.save();
            } else if (options.saveRequest){
                var o = button.ajaxOptions();
                o.beforeSend();
                options.saveRequest()
                    .success(o.success)
                    .error(o.error)
                ;
            }
        });

        var beforeunload = function () {
            var stillAttached = button.ui.parents()[button.ui.parents().length - 1].tagName.toLowerCase() == 'html';
            if (button.state !== 'saved' && stillAttached) {
                return options.unsavedMessage || "";
            }
        };
        COMMCAREHQ.bindBeforeUnload(beforeunload);
        return button;
    },
    initForm: function ($form, options) {
        var url = $form.attr('action'),
            button = SaveButton.init({
                unsavedMessage: options.unsavedMessage,
                save: function () {
                    button.ajax({
                        url: url,
                        type: 'POST',
                        dataType: 'json',
                        data: $form.serialize(),
                        success: options.success
                    });
                }
            }),
            fireChange = function () {
                button.fire('change');
            };
        $form.find('*').change(fireChange);
//        $form.on('textchange', 'input, textarea', fireChange);
        $form.find('input, textarea').bind('textchange', fireChange);
        return button;
    },
    message: {
        SAVE: 'Save',
        SAVING: 'Saving',
        SAVED: 'Saved',
        RETRY: 'Try Again',
        ERROR_SAVING: 'There was an error saving'
    }
};
