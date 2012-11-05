var CommCareUsersListHandler = function (o) {
    var self = this;
    self.total = o.total;
    self.page = o.page;
    self.limit = o.limit;
    self.max_page = Math.ceil(self.total/self.limit);

    self.list_elem = o.list_elem;
    self.cannot_share = o.cannot_share;
    self.list_url = o.list_url;
    self.show_inactive = o.show_inactive;

    self.init = function () {
        $(function () {
            self.users_list = $(self.list_elem);
            $.ajax({
                url: self.current_page,
                dataType: 'json',
                success: reloadList
            });
        });
    };



    var format_url = function(position) {
        var page = self.page + position;

        if (page < 0 || page > self.max_page) {
            return null;
        }
        return self.list_url +'?page=' + page +
            "&limit=" + self.limit +
            "&cannot_share=" + self.cannot_share +
            "&show_inactive=" + self.show_inactive;
    };

    self.current_page = format_url(0);
    self.next_page = format_url(1);
    self.previous_page = format_url(-1);

    var reloadList = function(data) {
        self.users_list.html(data.user_list_html);
    };

};