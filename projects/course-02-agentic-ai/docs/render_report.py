"""Build the offline decision report from the Markdown files next to this script."""
from base64 import b64encode
from html import escape
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
import re

from markdown_it import MarkdownIt

docs = Path(__file__).resolve().parent
repo = docs.parents[2]
sections = [
    ('overview', 'design-review.md'),
    ('project', 'project.md'),
    ('incident', 'reference-incident.md'),
    ('architecture', 'architecture.md'),
    ('prompts', 'specs/prompts.md'),
    ('context', 'specs/context.md'),
    ('memory', 'specs/memory.md'),
    ('caching', 'specs/caching.md'),
    ('evaluation', 'specs/evaluation.md'),
    ('permissions', 'specs/permissions.md'),
    ('coordination', 'specs/coordination.md'),
    ('execution', 'specs/execution.md'),
    ('experiments', 'experiments.md'),
    ('decisions', 'decisions.md'),
    ('record-handover', 'cases/restart/handover.md'),
    ('record-latency', 'cases/restart/latency.md'),
    ('record-actions', 'cases/restart/actions.md'),
    ('record-current', 'cases/restart/current.md'),
]
lookup = {docs / name: key for key, name in sections}
lookup[docs/'cases/restart'] = 'samples'
aliases = {
    ('overview', 'the-short-version-for-luís'): 'for-luis',
    ('overview', 'what-we-took-from-helloform'): 'helloform',
    ('memory', 'agreed-handover-evidence'): 'handover-evidence',
    ('context', 'agreed-shortening-a-shift-handover'): 'shortened-handover',
    ('memory', 'agreed-when-a-lesson-applies'): 'lesson-applicability',
    ('memory', 'agreed-who-can-correct-a-shared-lesson'): 'lesson-corrections',
    ('memory', 'agreed-when-a-source-is-deleted'): 'deleted-evidence',
    ('incident', 'when-a-reading-is-missing'): 'missing-reading',
    ('incident', 'the-wrongly-credited-restart'): 'wrongly-credited-restart',
}
md = MarkdownIt('commonmark', {'html': False}).enable('table')
diagrams = set()

def slug(value):
    return re.sub(r'[^\w -]', '', value.lower()).replace(' ', '-')

def render(key, name):
    file = docs / name
    text = file.read_text()
    match = re.search(r'^!\[([^\]]+)\]\(([^)]+)\)\n', text, flags=re.M)
    flow = ''
    if match:
        diagram = (file.parent / match[2]).resolve()
        data = b64encode(diagram.read_bytes()).decode()
        label = escape(text.splitlines()[0][2:])
        flow = (f'<details><summary>{escape(match[1])}: {label}</summary>'
                f'<img alt="{label} flow diagram" src="data:image/svg+xml;base64,{data}"></details>')
        text = text[:match.start()] + text[match.end():]
        diagrams.add(key)
    tokens = md.parse(text)
    for i, tok in enumerate(tokens):
        if tok.type == 'heading_open':
            level = int(tok.tag[1:])
            s = slug(tokens[i + 1].content)
            if level > 1:
                tok.attrSet('id', key + '-' + s)
                alt = aliases.get((key, s))
                if alt:
                    tok.meta['alias'] = alt
            if key != 'overview':
                tag = 'h' + str(level+1)
                tok.tag = tag
                tokens[i+2].tag = tag
        for child in tok.children or []:
            if child.type != 'link_open':
                continue
            dest = urlsplit(child.attrGet('href'))
            if dest.scheme:
                continue
            to = (file.parent / unquote(dest.path)).resolve() if dest.path else file
            assert to.exists(), (name, dest)
            if to in lookup:
                href = '#' + lookup[to] + ('-' + dest.fragment if dest.fragment else '')
            else:
                assert to.is_relative_to(repo), to
                href = ('https://github.com/jpboliv/meridian-project/blob/main/'
                        + quote(to.relative_to(repo).as_posix())
                        + ('#' + dest.fragment if dest.fragment else ''))
            child.attrSet('href', href)
    body = md.renderer.render(tokens, md.options, {})
    for tok in tokens:
        if alt := tok.meta.get('alias'):
            head = '<' + tok.tag + ' id="' + tok.attrGet('id') + '"'
            assert body.count(head) == 1
            body = body.replace(head, f'<span class="anchor" id="{alt}"></span>{head}')
    body = body.replace('<table>', '<div class="table-wrap"><table>').replace('</table>', '</table></div>')
    return body + flow

navigation = [
    ('Conversation', [('for-luis', 'For Luís'), ('overview-what-the-early-trials-showed','Observed so far'), ('helloform','Helloform decisions')]),
    ('Project', [('project','1 · Goals'), ('incident','2 · Three shifts'), ('architecture','3 · Information ownership')]),
    ('Model input', [('prompts','4 · Prompts'), ('context','5 · Context'), ('memory','6 · Memory'), ('caching','7 · Caching')]),
    ('Behavior', [('evaluation','8 · Evaluation'), ('permissions','9 · Permissions'), ('coordination','10 · Specialists'), ('execution','11 · Resume')]),
    ('Records', [('experiments','Trial records'), ('decisions','Decision log'), ('samples','Original case records')]),
]
nav = '<nav id="contents" aria-label="Report contents"><h2>In this report</h2>' + ''.join(
    '<p><span>' + group + '</span> ' + ' · '.join(f'<a href="#{k}">{escape(n)}</a>' for k,n in links) + '</p>'
    for group,links in navigation) + '</nav>'
style = '''
:root{color-scheme:light}*{box-sizing:border-box}html{scroll-padding-top:1rem}
body{max-width:56rem;margin:auto;padding:1rem;color:#193a38;background:#faf9f5;font:17px/1.55 system-ui,sans-serif}
header,nav,section{background:white;border:1px solid #ccdcd8;border-radius:12px;margin:1rem 0;padding:clamp(1rem,4vw,2.2rem)}
h1,h2,h3{line-height:1.2;text-wrap:balance}h1{font-size:2.2rem}h2{margin-top:1.8rem}h3{margin-top:1.6rem}
section>h2:first-child,nav>h2:first-child{margin-top:0}
a{color:#145e55;text-underline-offset:.15em}a:focus-visible,summary:focus-visible{outline:2px solid #145e55;outline-offset:.15em}
nav p{margin:.4rem 0}nav p span{display:inline-block;min-width:7.5em;font-weight:600}
details{margin:1.2rem 0}summary{cursor:pointer;color:#365f59}img{display:block;max-width:100%;height:auto;margin:1rem auto}
.table-wrap{overflow:auto}table{border-collapse:collapse;font-size:.94em;width:100%;margin:.7rem 0}
th,td{text-align:left;vertical-align:top;padding:.45rem .6rem;border-bottom:1px solid #ccdcd8}th{background:#edf6f4}
code{overflow-wrap:anywhere;font-size:.88em}.anchor{display:block}.back{display:block;margin-top:1.2rem;font-size:.87em}
@media print{body{padding:0;background:white;font-size:11pt}header,section{border:0;margin:0;padding:.4rem 0}nav,.back,summary{display:none}tr,h2,h3{break-inside:avoid}h2,h3{break-after:avoid}.table-wrap{overflow:visible}a{color:inherit}}
'''
pieces = ['<!doctype html><html lang="en"><head><meta charset="utf-8">'
          '<meta name="viewport" content="width=device-width,initial-scale=1">'
          '<title>Meridian | Specification and decision report</title><style>' + style + '</style></head><body>']
for key,name in sections:
    body = render(key,name)
    if key == 'overview':
        # Put navigation after the introduction, while keeping the short explanation first.
        mark = '<h2 id="overview-one-decision-from-start-to-finish">'
        left, right = body.split(mark, maxsplit=1)
        pieces.extend([f'<header id="overview">{left}</header>', nav, '<main><section aria-label="Review overview">' + mark + right + '</section>'])
    else:
        if key == 'record-handover':
            pieces.append('<section id="samples"><h2>Original records from the restart case</h2>'
                          '<p>These four synthetic files were the only case files available to the read-only shift. '
                          'The readings describe the previous shift unless the record names the current shift.</p></section>')
        pieces.append(f'<section id="{key}">{body}<a class="back" href="#contents">Back to contents</a></section>')
pieces.append('</main></body></html>\n')
doc = '\n'.join(pieces)
assert len(diagrams)==8
out = docs / 'decision-report.html'
out.write_text(doc, encoding='utf-8')
print(out)
