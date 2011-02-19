import HTMLParser

# hat tips: 
# http://stackoverflow.com/questions/3276040/how-can-i-use-the-python-htmlparser-library-to-extract-data-from-a-specific-div-t
# http://code.activestate.com/recipes/496787-extract-elements-with-id-attributes-from-html/
# This is pretty hacky. Not sure if it can be done more cleanly, but probably
class DivIdParser(HTMLParser.HTMLParser):
    
    def __init__(self, tag_id, tag_type="div"):
        HTMLParser.HTMLParser.__init__(self)
        self.recording = 0
        self._start_pos = 0
        self._end_pos = 0
        self._tag_id = tag_id
        self._tag_type = tag_type
        self._start_tag = "<%s>" % tag_type
        self._end_tag = "</%s>" % tag_type
        self._raw_html = ""
        
    def feed(self, data):
        self._raw_html += data
        #super(DivIdParser, self).feed(data) # old style class - not supported
        HTMLParser.HTMLParser.feed(self, data)
            
    def handle_starttag(self, tag, attributes):
        if tag != self._tag_type:
            return
        if self.recording:
            self.recording += 1
            return
        for name, value in attributes:
            if name == 'id' and value == self._tag_id:
                self._start_tag = self.get_starttag_text()
                self._start_pos = self.getpos()
                break
        else:
            return
        self.recording = 1
    
    def handle_endtag(self, tag):
        if self.recording:
            if tag == 'div':
                self.recording -= 1
                if self.recording == 0:
                    self._end_pos = self.getpos()
    
    def get_html(self):
        
        if self._start_pos and self._end_pos:
            vals = self._raw_html.split("\n")
            ret = [self._start_tag]
            for i in range(self._start_pos[0], self._end_pos[0]):
                start_index = self._start_pos[1] if i == self._start_pos[0] else 0
                end_index = self._end_pos[1] if i == self._end_pos[0] else len(vals[i])
                ret.append(vals[i][start_index:end_index])
            
            return "\n".join(ret)
        return ""


class ReportParser():
    def __init__(self, raw_html):
        self._title_parser = DivIdParser("report-title")
        self._title_parser.feed(raw_html)
        self._title_parser.close()
        self._body_parser = DivIdParser("report-content")
        self._body_parser.feed(raw_html)
        self._body_parser.close()
        
    def get_html(self):
        return "%(title)s\n%(body)s" % {"title": self._title_parser.get_html(),
                                        "body": self._body_parser.get_html()}
