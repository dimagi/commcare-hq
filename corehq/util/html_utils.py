from io import StringIO
from html.parser import HTMLParser


# Inspired by: https://stackoverflow.com/questions/753052/strip-html-from-strings-in-python
# Note that this should not be used where Sanitization is required, as removing one tag
# could create a new tag in the new output
def strip_tags(html):
    s = HTMLRemover()
    s.feed(html)
    return s.get_data()


class HTMLRemover(HTMLParser):
    def __init__(self):
        super().__init__()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, data):
        self.text.write(data)

    def get_data(self):
        return self.text.getvalue()
