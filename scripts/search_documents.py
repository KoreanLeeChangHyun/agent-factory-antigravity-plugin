#!/usr/bin/env python3
"""Search the live Original, Refined, Progress and Lessons Learned Document catalog."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from catalog_documents import (CATALOG_TYPES, TYPE_ALIASES, build_catalog, catalog_entry,
                               check_path, contract_entry, inventory, lesson_entry)
from storage.errors import ContractError


def snapshot(root, entry, observer=None):
    """Hash all package dependencies; reuse these bytes for search and section reads."""
    package = root / entry['packagePath']
    files = ([entry['packagePath']] if package.is_file() else
             [str((package / name).relative_to(root)) for name, shape in
              sorted(inventory(package, root).items()) if shape == 'file'])
    bodies = {path: (root / path).read_bytes() for path in files}
    if observer is not None:
        observer(bodies)
    hashes = {path: hashlib.sha256(body).hexdigest() for path, body in bodies.items()}
    revision = hashlib.sha256(json.dumps([entry, hashes], ensure_ascii=False,
                                       sort_keys=True).encode('utf-8')).hexdigest()
    return bodies, hashes, revision


def document_id(entry):
    """Identity includes type and scope; equal prose never merges authority domains."""
    return json.dumps([entry.get(key) for key in
                       ('documentType', 'category', 'domain', 'name', 'scope')], ensure_ascii=False)


def sections(text):
    """Index ATX headings and explicit HTML IDs outside fenced code, without summarizing."""
    headings, offset, fence, pending = [], 0, None, None
    used = {}
    for line in text.splitlines(keepends=True):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and not line[marker.end():].strip():
                fence = None
        elif fence is None:
            anchor = re.match(r'^\s*<a\s+id=[\"\']([^\"\']+)[\"\']\s*>\s*</a>\s*$', line)
            heading = re.match(r'^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$', line)
            if anchor:
                pending = (anchor[1], offset)
            elif heading:
                title = heading[2]
                slug = re.sub(r'[^\w\- ]', '', title.casefold()).replace(' ', '-')
                number = used.get(slug, 0)
                used[slug] = number + 1
                anchor_id = pending[0] if pending else slug + (f'-{number}' if number else '')
                headings.append(dict(anchor=anchor_id, heading=title, level=len(heading[1]),
                                     start=pending[1] if pending else offset))
                pending = None
            elif line.strip():
                pending = None
        offset += len(line)
    for index, heading in enumerate(headings):
        heading['end'] = next((other['start'] for other in headings[index + 1:]
                               if other['level'] <= heading['level']), len(text))
    return headings


def read_document(root, path, anchor=None, revision=None, documents_root=None, observer=None, *, catalog=None):
    """Read canonical bytes with dependency freshness and complete entry guidance."""
    identity_root = root.resolve(strict=True)
    root = (documents_root or root).resolve(strict=True)
    relative = Path(path)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Read path must be project-relative without traversal')
    check_path(root / relative, root)
    path = relative.as_posix()
    if len(relative.parts) >= 4 and relative.parts[:2] == ('docs', 'skills'):
        entry = catalog_entry(root, root.joinpath(*relative.parts[:3]), 'specification')
    else:
        entries = catalog if catalog is not None else build_catalog(identity_root, root)['documents']
        entry = next((item for item in entries
                      if path in (item.get('contentPaths') or [item['contentPath']])
                      or path == item['metadataPath']), None)
        if entry is not None and catalog is not None:
            # Reuse discovery, never stale metadata. Read the selected package live;
            # snapshot below still rebuilds every dependency hash before revision checks.
            package = root / entry['packagePath']
            location = entry.get('location')
            if entry['documentType'] == 'lessons-learned':
                entry = lesson_entry(root, package, identity_root)
            elif 'contract' in entry:
                entry = contract_entry(root, package)
            else:
                entry = catalog_entry(root, package, entry['documentType'])
            if location is not None:
                entry['location'] = location
    if entry is None:
        raise ValueError('Read path is not a canonical Document content path')
    bodies, hashes, current = snapshot(root, entry, observer)
    allowed = entry.get('contentPaths') or [entry['contentPath']]
    if path not in allowed and path != entry['metadataPath']:
        raise ValueError('Read path is not a Document text source')
    if revision is not None and revision != current:
        raise ValueError('Stale document revision; search/read the current source again')
    text = bodies[path].decode('utf-8')
    spans = sections(text)
    selected = [item for item in spans if item['anchor'] == anchor] if anchor else []
    if anchor and len(selected) != 1:
        raise ValueError('Section anchor missing or ambiguous; read the full source')
    start, end = (selected[0]['start'], selected[0]['end']) if selected else (0, len(text))
    entry_path = entry['contentPath'] or entry['metadataPath']
    return dict(schemaVersion='0.1.0', kind='document-read', document=entry,
                documentId=document_id(entry),
                path=path, anchor=anchor, revision=current, sha256=hashes[path],
                start=start, end=end, text=text[start:end], sections=spans,
                entryPath=entry_path, entryText=(bodies[entry_path].decode('utf-8')
                                               if anchor or path != entry_path else None),
                dependencies=hashes, partial=bool(anchor),
                guidance='Selected sections are discovery aids. Read linked rules, decisions and exceptions before acting.')


def search(root: Path, query: str, document_type=None, category=None, limit=20, scope=None, documents_root=None, match='all', offset=0, observer=None, *, catalog=None) -> dict:
    terms = [term.casefold() for term in query.split() if term]
    if not terms:
        raise ValueError("Search query must contain non-whitespace text")
    if limit is not None and (limit < 1 or limit > 100):
        raise ValueError("Search limit must be between 1 and 100")
    if match not in ('all', 'any') or type(offset) is not int or offset < 0:
        raise ValueError('Expected match all/any and nonnegative offset')
    document_type = TYPE_ALIASES.get(document_type, document_type)
    identity_root = root.resolve(strict=True)
    root = (documents_root or root).resolve(strict=True)
    matches = []
    entries = catalog if catalog is not None else build_catalog(identity_root, root)['documents']
    for entry in entries:
        if document_type and entry["documentType"] != document_type:
            continue
        if category and entry["category"] != category:
            continue
        if scope and entry.get("scope", entry["metadata"].get("scope")) != scope:
            continue
        searchable = json.dumps(entry["metadata"], ensure_ascii=False)
        bodies, hashes, revision = snapshot(root, entry, observer)
        paths = entry.get("contentPaths") or ([entry["contentPath"]] if entry["contentPath"] else [])
        for path in paths:
            searchable += "\n" + bodies[path].decode('utf-8')
        folded = searchable.casefold()
        matched_terms = [term for term in terms if term in folded]
        if not matched_terms or (match == 'all' and len(matched_terms) != len(terms)):
            continue
        result = {key: value for key, value in entry.items() if key != "metadata"}
        for field in ("scope", "status"):
            if field not in result and field in entry["metadata"]:
                result[field] = entry["metadata"][field]
        result["score"] = sum(folded.count(term) for term in terms)
        result.update(documentId=document_id(entry), revision=revision,
                      dependencies=hashes, matchedTerms=matched_terms)
        result['sources'] = []
        for path in paths:
            text = bodies[path].decode('utf-8')
            if any(term in text.casefold() for term in terms):
                result['sources'].append(dict(path=path, sha256=hashes[path], sections=[
                    item for item in sections(text) if any(term in text[item['start']:item['end']].casefold()
                                                          for term in terms)]))
        matches.append(result)
    matches.sort(
        key=lambda item: (
            -(len(item['matchedTerms']) if match == 'any' else 0), -item["score"], item["documentType"], item["category"],
            item["domain"] or "", item["name"],
        )
    )
    # Internal callers can consume the already computed complete result set once.
    # CLI pagination retains its size/offset contract.
    page = matches[offset:] if limit is None else matches[offset:offset + limit]
    return {
        "schemaVersion": "0.1.0",
        "kind": "document-search-results",
        "query": query,
        "count": len(page),
        "results": page,
        "totalCount": len(matches), "offset": offset,
        "nextOffset": offset + limit if limit is not None and offset + limit < len(matches) else None,
        "match": match,
    }


def read_selections(root, selections, documents_root=None):
    """Read explicit sources in order; publish no partial or mixed-revision bundle."""
    from execution.document_context import validate

    selections = validate({'selections': selections})['selections']
    reads, revisions, catalog = [], {}, None
    for item in selections:
        parts = Path(item['path']).parts
        if not (len(parts) >= 4 and parts[:2] == ('docs', 'skills')) and catalog is None:
            catalog = build_catalog(root, documents_root)['documents']
        read = read_document(root, item['path'], item.get('anchor'), item.get('revision'),
                             documents_root, catalog=catalog)
        if revisions.setdefault(read['entryPath'], read['revision']) != read['revision']:
            raise ValueError('Document revision changed within batch; read current sources again')
        reads.append(read)
    return dict(schemaVersion='0.1.0', kind='document-read-context', reads=reads, candidates=[])


def encode_result(result, *, compact=False):
    """Keep legacy CLI output by default; opt in to lossless source sharing."""
    if not compact:
        return json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    inline = json.dumps(result, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    if result.get('kind') in ('document-read', 'document-read-context'):
        from execution.document_context import encode_context

        bundle = result if result['kind'] == 'document-read-context' else dict(
            schemaVersion=result['schemaVersion'], kind='document-read-context',
            reads=[result], candidates=[])
        shared, metrics = encode_context(bundle)
        if (metrics['contextLayout'] == 'shared-sources-v1'
                and len(shared.encode('utf-8')) < len(inline.encode('utf-8'))):
            return shared
    return inline


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--query")
    operation.add_argument("--read-path", help="Canonical project-relative Document or docs/skills text path")
    operation.add_argument("--read-selections-file", type=Path,
                           help="JSON array of canonical path, optional anchor/revision objects; one complete read bundle")
    parser.add_argument("--anchor", help="Read one ATX section by explicit HTML ID or heading slug; retains complete entry guidance")
    parser.add_argument("--revision", help="Require a matching package revision when reading; stale input fails closed")
    parser.add_argument("--match", choices=('all', 'any'), default='all', help="all preserves legacy AND search; any explicitly explores partial lexical matches")
    parser.add_argument("--offset", type=int, default=0, help="Result page offset; totalCount and nextOffset expose all matches")
    parser.add_argument("--type", choices=(*CATALOG_TYPES, *TYPE_ALIASES))
    parser.add_argument("--category")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--scope")
    parser.add_argument("--documents-root", type=Path, help="Physical workspace containing docs; runtime identity stays --project-root")
    parser.add_argument("--compact", action="store_true", help="Compact JSON; reads may use shared-sources-v1, retaining complete entry guidance and metadata")
    args = parser.parse_args()
    try:
        if args.read_path:
            results = read_document(args.project_root, args.read_path, args.anchor, args.revision, args.documents_root)
        else:
            if args.anchor is not None or args.revision is not None:
                raise ValueError('--anchor and --revision require --read-path; batch selections carry their own values')
            if args.read_selections_file is not None:
                selections = json.loads(args.read_selections_file.read_text(encoding='utf-8'))
                results = read_selections(args.project_root, selections, args.documents_root)
            else:
                results = search(args.project_root, args.query, args.type, args.category, args.limit, args.scope, args.documents_root, args.match, args.offset)
        output = encode_result(results, compact=args.compact)
    except (OSError, TypeError, ValueError, ContractError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
