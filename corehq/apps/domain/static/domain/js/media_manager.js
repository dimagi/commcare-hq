var MediaFile = function(data) {
    var self = this;
    self.license = ko.observable(data.license || 'public');
    self.shared = ko.observable(data.shared);
    self.url = ko.observable(data.url); // so we can preview it; we never change .url
    self.m_id = data.m_id;
    self.tags = ko.observable(data.tags.join(' '));
    self.type = data.type;
    self.image = ko.observable(self.type == 'CommCareImage');
    self.audio = ko.observable(self.type == 'CommCareAudio');
    self.other = ko.observable(self.type == 'CommCareMultimedia');
};

var MediaManager = function(data, licenses) {
    var self = this;
    self.media = [];
    self.licenses = [];
    var settingShared = false;
    for (var i = 0; i < licenses.length; i++) {
        self.licenses.push({name: licenses[i][1], code: licenses[i][0]});
    }
    for (var i = 0; i < data.length; i++) {
        self.media.push(new MediaFile(data[i]));
    }

    self.allShared = ko.computed({
        read: function() {
            var firstUnchecked = ko.utils.arrayFirst(self.media, function(m) {
                return m.shared() == false;
            });
            return firstUnchecked == null;
        },
        write: function(value) {
            ko.utils.arrayForEach(self.media, function(m) {
                m.shared(value);
            });
        }
    });
}