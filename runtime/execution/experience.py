"""Read-only project evidence: original run files and the existing lesson lifecycle.

No second knowledge store, inferred authority, automatic publication or persistent index.
Pages are a presentation boundary; every match and every source character stays reachable.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from storage import paths
from storage.errors import ContractError
from storage.files import AGENT_ID, safe_read_bytes, safe_read_json

RUN_ID = re.compile(r'run-[A-Za-z0-9][A-Za-z0-9._-]*\Z')
RUN_FILES = {'request': 'request.md', 'result': 'result.md', 'receipt': 'receipt.json',
             'facts': 'lesson-facts.jsonl'}


def fail(message):
    raise ContractError('experience_invalid', message)


def source(value, *, pinned=False):
    if not isinstance(value, dict):
        fail('Expected an evidence source')
    kind = value.get('kind')
    fields = {'kind', 'revision'}
    if kind == 'run':
        fields |= {'agentId', 'runId', 'document'}
        if (not isinstance(value.get('agentId'), str) or not AGENT_ID.fullmatch(value['agentId'])
                or not isinstance(value.get('runId'), str) or not RUN_ID.fullmatch(value['runId'])
                or value.get('document') not in RUN_FILES):
            fail('Expected a project run identity and a supported document')
    elif kind == 'lesson':
        fields.add('id')
        if not isinstance(value.get('id'), str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,100}', value['id']):
            fail('Expected a lesson identity')
    elif kind == 'document':
        fields |= {'path', 'anchor'}
        path = value.get('path')
        if (not isinstance(path, str) or not path.startswith('docs/') or '\\' in path
                or '..' in Path(path).parts or '\0' in path):
            fail('Expected a canonical project Document path')
        if 'anchor' in value and (not isinstance(value['anchor'], str) or not value['anchor']):
            fail('Expected a nonempty section anchor')
    else:
        fail('Unsupported evidence source')
    if set(value) - fields:
        fail('Unexpected source fields')
    revision = value.get('revision')
    if (pinned or revision is not None) and (not isinstance(revision, str) or not re.fullmatch(r'[a-f0-9]{64}', revision)):
        fail('Expected the exact source revision')
    return dict(value)


def number(value, default, *, positive=False):
    if value is None:
        return default
    if type(value) is not int or value < (1 if positive else 0):
        fail('Invalid page position or length')
    return value


def run_directory(root, ref):
    binding = paths.resolve(root)
    if not binding['registered']:
        fail('The project has no registered runtime')
    folder = Path(binding['agentsRoot']) / ref['agentId'] / 'runs' / ref['runId']
    paths.inspect(folder)
    state = safe_read_json(folder / 'state.json')
    if state.get('agentId') != ref['agentId'] or state.get('runId') != ref['runId']:
        fail('Run identity does not match its project directory')
    return folder, state


def read_evidence(root, ref, documents_root=None):
    """Read and revision-check full source data; callers choose presentation pages."""
    ref = source(ref)
    identity = {key: value for key, value in ref.items() if key != 'revision'}
    if ref['kind'] == 'document':
        from search_documents import read_document
        read = read_document(root, ref['path'], ref.get('anchor'), ref.get('revision'), documents_root)
        return {'source': {**identity, 'revision': read['revision']}, 'title': read['path'],
                'text': read['text'], 'document': read, 'revision': read['revision']}
    if ref['kind'] == 'run':
        folder, state = run_directory(root, ref)
        file = folder / RUN_FILES[ref['document']]
        text = safe_read_bytes(file, None).decode('utf-8')
        record = {'agentId': ref['agentId'], 'runId': ref['runId'], 'status': state.get('status'),
                  'createdAt': state.get('createdAt'), 'documentContext': state.get('documentContext'),
                  'documentContextAttempts': state.get('documentContextAttempts')}
        title = f"{ref['agentId']} / {ref['runId']} / {ref['document']}"
        revision = hashlib.sha256(text.encode('utf-8')).hexdigest()
    else:
        import lessons
        record = lessons.find(root, ref['id'], documents_root)
        text = json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2)
        title = record['title']
        revision = hashlib.sha256(text.encode('utf-8')).hexdigest()
    if ref.get('revision') and ref['revision'] != revision:
        raise ContractError('experience_stale', 'The source changed; read and select its current version again')
    return {'source': {**identity, 'revision': revision}, 'revision': revision,
            'title': title, 'text': text, 'record': record,
            'authority': 'Historical evidence only. Retrieval is not rule application, approval or publication.'}


def snippet(text, words):
    folded = text.casefold()
    if not all(word in folded for word in words):
        return None
    # Display excerpts only; the exact full source is available through read.
    position = min((folded.find(word) for word in words), default=0)
    start = max(0, position - 100)
    return {'excerpt': text[start:start + 360], 'start': start,
            'score': sum(folded.count(word) for word in words)}


def search_runs(root, query):
    binding = paths.resolve(root)
    if not binding['registered']:
        return [], []
    agents = Path(binding['agentsRoot'])
    words = query.casefold().split()
    rows, warnings = [], []
    if not agents.exists():
        return rows, warnings
    paths.inspect(agents)
    for agent in sorted(agents.iterdir()):
        if not AGENT_ID.fullmatch(agent.name):
            continue
        try:
            paths.inspect(agent)
            runs = agent / 'runs'
            if not runs.exists():
                continue
            paths.inspect(runs)
            for folder in sorted(runs.iterdir(), reverse=True):
                if not RUN_ID.fullmatch(folder.name):
                    continue
                for document, filename in RUN_FILES.items():
                    ref = {'kind': 'run', 'agentId': agent.name, 'runId': folder.name, 'document': document}
                    try:
                        paths.inspect(folder)
                        if not (folder / filename).exists():
                            continue
                        value = read_evidence(root, ref)
                        match = snippet(value['text'], words)
                        if match is not None:
                            rows.append({'source': value['source'], 'title': value['title'],
                                         'status': value['record']['status'], **match})
                    except (ValueError, OSError, ContractError) as error:
                        warnings.append({'source': ref, 'error': str(error)})
        except (ValueError, OSError, ContractError) as error:
            warnings.append({'agentId': agent.name, 'error': str(error)})
    rows.sort(key=lambda row: (row['score'], row['source']['runId'], row['source']['agentId']), reverse=True)
    return rows, warnings


def search_lessons(root, query, scope=None):
    import lessons
    words = query.casefold().split()
    rows = []
    for record in lessons.records(root):
        if scope and record.get('scope') != scope:
            continue
        text = json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2)
        match = snippet(text, words)
        if match is None:
            continue
        applications = record.get('applications', [])
        rows.append({'source': {'kind': 'lesson', 'id': record['id'],
                                'revision': hashlib.sha256(text.encode('utf-8')).hexdigest()},
                     'title': record['title'], 'status': record['status'], 'scope': record['scope'],
                     'occurrences': len(record.get('occurrences', [])),
                     'candidates': len(record.get('candidates', [])),
                     'publications': len(record.get('publications', [])),
                     'outcomes': {name: sum(item.get('outcome') == name for item in applications)
                                  for name in ('success', 'recurrence', 'correction', 'unused')}, **match})
    rows.sort(key=lambda row: (-row['score'], row['title'], row['source']['id']))
    return rows, []


def operate(root, action, payload):
    if not isinstance(payload, dict):
        fail('Expected an object payload')
    if action == 'sync-status':
        if payload:
            fail('Sync status accepts no mutation or path parameters')
        from sync_documents import HOST_DIRECTORIES, status
        # Observe existing host installations only; opening the view creates nothing.
        hosts = tuple(host for host, directory in HOST_DIRECTORIES.items() if (root / directory).exists())
        return status(root, hosts=hosts)
    if action in ('runs', 'lessons'):
        query = payload.get('query', '')
        if not isinstance(query, str) or set(payload) - {'query', 'offset', 'limit', 'scope'}:
            fail('Invalid search payload')
        scope = payload.get('scope')
        if scope is not None and (not isinstance(scope, str) or not scope.strip()):
            fail('Invalid lesson scope')
        offset = number(payload.get('offset'), 0)
        limit = number(payload.get('limit'), 30, positive=True)
        rows, warnings = search_runs(root, query) if action == 'runs' else search_lessons(root, query, scope)
        return {'entries': rows[offset:offset + limit], 'totalCount': len(rows), 'offset': offset,
                'nextOffset': offset + limit if offset + limit < len(rows) else None, 'warnings': warnings}
    if action not in ('read', 'select') or set(payload) - {'source', 'offset', 'length'}:
        fail('Unsupported operation or fields')
    value = read_evidence(root, payload.get('source'))
    if action == 'select':
        ref = value['source']
        context = ({'selections': [{key: ref[key] for key in ('path', 'anchor', 'revision') if key in ref}]}
                   if ref['kind'] == 'document' else {'evidenceSelections': [ref]})
        return {'title': value['title'], 'source': ref, 'documentContext': context}
    offset = number(payload.get('offset'), 0)
    default_length = (len(value['text']) or 1) if value['source']['kind'] == 'document' else 8000
    length = number(payload.get('length'), default_length, positive=True)
    text = value['text']
    # Lesson lifecycle data is structural and complete; source prose remains paged.
    record = value.get('record')
    return {**{key: value[key] for key in ('source', 'revision', 'title')},
            **({'record': record} if record is not None else {}),
            **({'document': value['document']} if 'document' in value else {}),
            'text': text[offset:offset + length], 'offset': offset, 'totalChars': len(text),
            'nextOffset': offset + length if offset + length < len(text) else None}
