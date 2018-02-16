/* eslint-disable no-control-regex */
hqDefine('sms/js/chat', function () {
    var initialPageData = hqImport('hqwebapp/js/initial_page_data');
    $(function() {
        function resize_messages() {
            var body_height = $("body").height();
            var chat_header_height = $("#chat_header").height();
            var chat_footer_height = $("#chat_footer").height();
            $("#chat_messages").height(body_height - chat_header_height - chat_footer_height);
        }
        function MessageHistoryChoice(description, utc_timestamp) {
            var self = this;
            self.description = description;
            self.utc_timestamp = Date.parse(utc_timestamp); // The number of milliseconds since the Unix epoch
            self.selected = ko.observable(false);
        }
        function ChatMessage(sender, text, timestamp, utc_timestamp, seen) {
            var self = this;
            self.sender = sender;
            self.text = text;
            self.timestamp = timestamp;
            self.utc_timestamp = Date.parse(utc_timestamp); // The number of milliseconds since the Unix epoch
            self.seen_text = ko.observable("");
            // only pertains to messages that have not been read yet upon opening the window
            self.unread_message = false;
            self.set_seen_text = function (seen) {
                if (seen) {
                    self.seen_text("");
                } else {
                    self.seen_text(String.fromCharCode(9830));
                }
            };
            self.set_seen_text(seen);
        }
        function ChatWindowViewModel() {
            var self = this;
            self.original_title = document.title;
            self.message_length = ko.observable("0 / 160");
            self.messages = ko.observableArray([]);
            self.latest_message_utc_timestamp = null;
            self.latest_timeout_handle = null;
            self.title_timeout_handle = null;
            self.title_flag = true;
            self.is_focused = true;
            self.message_count = ko.observable(0);
            self.message_count_threshold = initialPageData.get('message_count_threshold');
            self.first_update = true;
            self.last_read_message_utc_timestamp = null;
            self.allow_highlights_to_disappear = false;

            //After we send a message, we need to wait for it to actually be sent
            //before it shows up in the history. Normally, we update the chat
            //history every regular_update_interval milliseconds. But right after
            //we send a message, we'll update the chat history every
            //quick_update_interval milliseconds (and do it the number of times
            //specified by quick_update_cycles), and then go back to updating on the
            //regular_update_interval. This makes messages show up faster in the
            //chat history after you click Send.
            self.quick_update_countdown = 0;
            self.quick_update_cycles = 15;
            self.regular_update_interval = 15000;
            self.quick_update_interval = 1000;
            self.update_messages_timeout_handle = null;
            self.update_in_progress = false;

            self.history_choices = ko.observableArray([]);
            var initial_history_choices = initialPageData.get('history_choices');
            for (var choice in initial_history_choices) {
                self.history_choices.push(
                    new MessageHistoryChoice(
                        initial_history_choices[choice].description,
                        initial_history_choices[choice].timestamp
                    )
                );
            }
            self.selected_history_choice = ko.observable();
            // false until the user selects one of the history choices
            self.history_choice_selected = false;
            self.update_history_choice = function (i, set_selected) {
                if (set_selected) {
                    self.history_choice_selected = true;
                }
                for (var j = 0; j < self.history_choices().length; j++) {
                    var entry = self.history_choices()[j];
                    if (i === j) {
                        entry.selected(true);
                        self.selected_history_choice(entry);
                    } else {
                        entry.selected(false);
                    }
                }
            };
            self.update_history_choice(0, false);

            self.update_messages = function (set_next_timeout) {
                self.update_in_progress = true;
                var payload = {
                    contact_id: initialPageData.get('contact_id')
                };
                if (self.latest_message_utc_timestamp !== null) {
                    payload.start_date = self.latest_message_utc_timestamp;
                }
                $.ajax({
                    url: initialPageData.reverse('api_history'),
                    data: payload,
                    async: true,
                    dataType: "json",
                    success: function (data) {
                        var chat_message = null;
                        var requires_notification = false;
                        for (var i = 0; i < data.length; i++) {
                            chat_message = new ChatMessage(
                                data[i].sender,
                                data[i].text,
                                data[i].timestamp,
                                data[i].utc_timestamp,
                                self.first_update || self.is_focused || data[i].sent_by_requester
                            );
                            if (!data[i].sent_by_requester) {
                                requires_notification = true;
                            }
                            self.latest_message_utc_timestamp = data[i].utc_timestamp;
                            if (self.first_update) {
                                if ((self.last_read_message_utc_timestamp === null) || (chat_message.utc_timestamp > self.last_read_message_utc_timestamp)) {
                                    chat_message.set_seen_text(false);
                                    chat_message.unread_message = true;
                                }
                            }
                            self.messages.push(chat_message);
                        }
                        if (!self.first_update && data.length > 0 && requires_notification) {
                            if (self.is_focused) {
                                self.start_new_message_notification(4);
                            } else {
                                self.start_new_message_notification(null);
                            }
                        }
                        if (data.length > 0) {
                            var scrollHeight = $("#chat_messages").prop("scrollHeight");
                            $("#chat_messages").scrollTop(scrollHeight);
                        }
                        if (self.first_update) {
                            self.first_update = false;
                        } else {
                            self.message_count(self.message_count() + data.length);
                            if (self.message_count() >= self.message_count_threshold) {
                                $("#message_count").css("background-color", "#F00");
                            }
                        }
                    },
                    complete: function () {
                        if (set_next_timeout) {
                            var time_to_wait = self.regular_update_interval;
                            if (self.quick_update_countdown > 0) {
                                self.quick_update_countdown--;
                                time_to_wait = self.quick_update_interval;
                            }
                            self.update_messages_timeout_handle = setTimeout(self.update_messages_timeout, time_to_wait);
                        }
                        self.update_in_progress = false;
                    },
                });
            };
            self.send_message = function () {
                $("#send_sms_button").prop("disabled", true);
                var request = $.ajax({
                    url: initialPageData.reverse('api_send_sms'),
                    type: "POST",
                    data: {
                        contact_id: initialPageData.get('contact_id'),
                        vn_id: initialPageData.get('vn_id'),
                        chat: "true",
                        text: $("#text_box").val()
                    }
                });
                request.done(function (response) {
                    if (response === "OK") {
                        $("#text_box").val("");
                        self.update_message_length(null);
                        self.quick_update_countdown = self.quick_update_cycles;
                        if (!self.update_in_progress) {
                            //If the update is not in progress, then force a new
                            //update to start immediately.
                            clearTimeout(self.update_messages_timeout_handle);
                            self.update_messages_timeout();
                        }
                    }
                });
                request.always(function () {
                    $("#send_sms_button").prop("disabled", false);
                });
            };
            self.update_messages_timeout = function () {
                self.update_messages(true);
            };
            self.get_max_message_length = function () {
                var msg = $("#text_box").val();
                var is_ascii = /^[\x00-\x7F]*$/.test(msg);
                if (is_ascii) {
                    return 160;
                } else {
                    return 70;
                }
            };
            self.update_message_length = function () {
                setTimeout(function () {
                    var len = $("#text_box").val().length;
                    var max_len = self.get_max_message_length();
                    self.message_length(len + " / " + max_len);
                    if (len > max_len) {
                        $("#message_length_label").css("background-color", "#F00");
                    } else {
                        $("#message_length_label").css("background-color", "#FFF");
                    }
                }, 250);
            };
            self.start_new_message_notification = function (num_seconds) {
                //num_seconds should be null to flash the window until it receives focus again
                //otherwise num_seconds is the number of seconds to flash the window
                self.stop_new_message_notification();
                self.flash_on();
                self.title_flag = false;
                self.title_timeout_handle = setInterval(function () {
                    self.title_flag = !self.title_flag;
                    if (self.title_flag) {
                        self.flash_off();
                    } else {
                        self.flash_on();
                    }
                }, 1000);
                if (typeof (num_seconds) === typeof (1)) {
                    setTimeout(function () {
                        self.stop_new_message_notification();
                    }, num_seconds * 1000);
                }
            };
            self.stop_new_message_notification = function () {
                if (self.title_timeout_handle !== null) {
                    clearTimeout(self.title_timeout_handle);
                    self.title_timeout_handle = null;
                }
                self.flash_off();
            };
            self.flash_on = function () {
                document.title = "(" + gettext('New Message') + ") - " + self.original_title;
                $("body").css("background-color", "#6060FF");
            };
            self.flash_off = function () {
                document.title = self.original_title;
                $("body").css("background-color", "#F0F0F0");
            };
            self.enter_focus = function () {
                self.stop_new_message_notification();
                self.is_focused = true;
                if (self.allow_highlights_to_disappear) {
                    setTimeout(function () {
                        $(".highlight_bullet").text("");
                    }, 5000);
                }
            };
            self.leave_focus = function () {
                self.is_focused = false;
            };
            self.reset_message_count = function () {
                self.message_count(0);
                $("#message_count").css("background-color", "#FFF");
            };
            self.update_last_read_message = function () {
                $.ajax({
                    url: initialPageData.reverse('api_last_read_message'),
                    type: "GET",
                    async: false,
                    data: {
                        contact_id: "initialPageData.get('contact_id')",
                    },
                    dataType: "json",
                    success: function (data) {
                        try {
                            var timestamp = Date.parse(data.message_timestamp);
                            if (isNaN(timestamp)) {
                                self.last_read_message_utc_timestamp = null;
                            } else {
                                self.last_read_message_utc_timestamp = timestamp;
                            }
                        } catch (err) {
                            //we'll just treat everything as not having been read yet
                            self.last_read_message_utc_timestamp = null;
                        }
                    },
                });
            };
            setTimeout(function () {
                self.allow_highlights_to_disappear = true;
            }, 60000);
        }
        var chat_window_view_model = new ChatWindowViewModel();
        ko.applyBindings(chat_window_view_model);
        $(window).resize(resize_messages);
        $(window).focus(chat_window_view_model.enter_focus);
        $(window).blur(chat_window_view_model.leave_focus);
        chat_window_view_model.update_last_read_message();
        chat_window_view_model.update_messages_timeout();
        $("#text_box").on("paste", chat_window_view_model.update_message_length);
        $("#text_box").keyup(chat_window_view_model.update_message_length);
        resize_messages();
    });
});
