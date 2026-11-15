import re
import sys
from html.parser import HTMLParser
from pathlib import Path


class SVGElements(HTMLParser):
    """Count HTML/SVG elements rather than markup inside comments."""

    def __init__(self):
        super().__init__()
        self.tags = set()
        self.stack = []
        self.svg_depth = 0
        self.closed_svg = False
        self.circles = 0
        self.paths = 0
        self.rotations = 0
        self.motions = 0
        self.animations = 0
        self.content = []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag)
        attributes = dict(attrs)
        parent_hidden = bool(self.stack and self.stack[-1][1])
        style = attributes.get('style') or ''
        hidden = (parent_hidden or tag in {'template', 'head', 'noscript'}
                  or 'hidden' in attributes
                  or bool(re.search(r'(?:display\s*:\s*none|visibility\s*:\s*hidden)',
                                    style, re.IGNORECASE)))
        in_body = any(parent == 'body' for parent, _, _ in self.stack)
        visible_svg = tag == 'svg' and in_body and not hidden
        if not hidden:
            self.content.append(self.get_starttag_text())
        if visible_svg:
            self.svg_depth += 1
        if self.svg_depth and not hidden:
            if tag == 'circle':
                self.circles += 1
            elif tag == 'path':
                self.paths += 1
            elif tag == 'animate':
                self.animations += 1
            elif tag == 'animatetransform':
                animation_type = (attributes.get('type') or '').lower()
                self.rotations += animation_type == 'rotate'
                self.motions += animation_type in {'translate', 'scale'}
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
                       'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append((tag, hidden, visible_svg))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                removed = self.stack[index:]
                del self.stack[index:]
                self.svg_depth -= sum(visible_svg for _, _, visible_svg in removed)
                if tag == 'svg' and removed[0][2]:
                    self.closed_svg = True
                break

    def handle_data(self, data):
        if not self.stack or not self.stack[-1][1]:
            self.content.append(data)


path = Path(sys.argv[1]) / 'crocodile.html'
assert path.is_file(), 'missing crocodile.html'
parser = SVGElements()
html = path.read_text(encoding='utf-8')
parser.feed(html)
parser.close()
assert {'html', 'body', 'svg'} <= parser.tags and parser.closed_svg
assert 'script' not in parser.tags
content = ''.join(parser.content).lower()
clean = html.lower().replace('http://www.w3.org/', '').replace('https://www.w3.org/', '')
assert 'http://' not in clean and 'https://' not in clean
assert parser.circles >= 2
assert parser.paths >= 3
assert parser.rotations >= 2, 'wheels need animateTransform rotate'
assert parser.animations + parser.motions >= 1, 'legs/body need an animation'
assert 'crocodile' in content or 'croc' in content or '鳄鱼' in content
