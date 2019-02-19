hqDefine('domain/js/media_manager', [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    initialPageData
) {
    var MediaFile = function (data) {
        var self = {};
        self.license = ko.observable(data.license || 'public');
        self.shared = ko.observable(data.shared);
        self.url = ko.observable(data.url); // so we can preview it; we never change .url
        self.m_id = data.m_id;
        self.tags = ko.observable(data.tags.join(' '));
        self.type = data.type;
        self.image = ko.observable(self.type === 'CommCareImage');
        self.audio = ko.observable(self.type === 'CommCareAudio');
        self.other = ko.observable(self.type === 'CommCareMultimedia');
        return self;
    };

    var mediaManager = function (data, licenses) {
        var self = {};
        self.media = [];
        self.licenses = [];
        var i;
        for (i = 0; i < licenses.length; i++) {
            self.licenses.push({name: licenses[i][1], code: licenses[i][0]});
        }
        for (i = 0; i < data.length; i++) {
            self.media.push(new MediaFile(data[i]));
        }

        self.allShared = ko.computed({
            read: function () {
                var firstUnchecked = ko.utils.arrayFirst(self.media, function (m) {
                    return m.shared() === false;
                });
                return firstUnchecked === null;
            },
            write: function (value) {
                ko.utils.arrayForEach(self.media, function (m) {
                    m.shared(value);
                });
            },
        });

        return self;
    };

    $(function () {
        $('#update-media-sharing-settings').koApplyBindings(mediaManager(
            initialPageData.get('media'), initialPageData.get('licenses')
        ));
    });
});
