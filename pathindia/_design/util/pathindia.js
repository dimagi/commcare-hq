var PathIndiaReport = function (doc) {
    var self = this;
    self.doc = doc;
    self.form = (doc.form) ? doc.form : doc;
    self.data = {};
};