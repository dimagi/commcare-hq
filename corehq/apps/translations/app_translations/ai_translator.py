"""AI translation of app content via the bulk app translation pipeline."""
import re

HTML_TAG_PATTERN = r'<[/!]?\w+(?:\s+[^>]*)?/?>'
URL_PATTERN = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
MARKDOWN_BULLET_PATTERN = r'^\s{0,3}[-*+] '
MARKDOWN_NUMBERED_PATTERN = r'^\s{0,3}\d+[.)] '
MARKDOWN_HEADING_PATTERN = r'^\s{0,3}#{1,6} '
MARKDOWN_LINK_PATTERN = r'\[[^\]]*\]\([^)]*\)'


def _markdown_signature(text):
    """Counts of the markdown markers CommCare renders on mobile.

    Counts, not positions — a translation may reorder sentences but not
    drop or add markers.
    """
    return (
        text.count('**'),
        # a run of 2+ underscores is a fill-in-the-blank line that may
        # be resized in translation, not __emphasis__ pairs
        len(re.findall(r'_{2,}', text)),
        len(re.findall(MARKDOWN_BULLET_PATTERN, text, re.MULTILINE)),
        len(re.findall(MARKDOWN_NUMBERED_PATTERN, text, re.MULTILINE)),
        len(re.findall(MARKDOWN_HEADING_PATTERN, text, re.MULTILINE)),
        len(re.findall(MARKDOWN_LINK_PATTERN, text)),
    )


def is_valid_app_translation(source, translated):
    """Check that a translation preserves the source's structure:
    ``<output/>`` references, HTML tags, URLs and markdown markers."""
    if not translated or not isinstance(translated, str):
        return False

    source_tags = re.findall(HTML_TAG_PATTERN, source)
    translated_tags = re.findall(HTML_TAG_PATTERN, translated)
    if len(source_tags) != len(translated_tags):
        return False
    if source_tags:
        def tag_info(tags):
            return [re.match(r'<(/?)(\w+)', tag).groups()
                    for tag in tags if re.match(r'<(/?)(\w+)', tag)]
        if tag_info(source_tags) != tag_info(translated_tags):
            return False
        # <output .../> references must survive byte-for-byte,
        # attributes included — a changed value breaks the form
        source_outputs = [t for t in source_tags if t.startswith('<output')]
        translated_outputs = [t for t in translated_tags if t.startswith('<output')]
        if source_outputs != translated_outputs:
            return False

    source_urls = re.findall(URL_PATTERN, source)
    if source_urls:
        # trailing punctuation is context, not URL — the regex swallows
        # e.g. the closing paren of a markdown link or a sentence period
        strip = '.\\),;:!?\'"'
        if ({u.rstrip(strip) for u in source_urls}
                != {u.rstrip(strip) for u in re.findall(URL_PATTERN, translated)}):
            return False

    if _markdown_signature(source) != _markdown_signature(translated):
        return False
    return True
