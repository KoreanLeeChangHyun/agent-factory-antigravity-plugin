"""Agent Factory ERD v1: validate authored JSON and render inert, self-contained SVG."""
from __future__ import annotations

from html import escape
import math
import unicodedata

VERSION = "1"
CARDINALITIES = ("1", "0..1", "1..*", "0..*")
STYLES = """
svg{--bg:#ffffff;--panel:#ffffff;--head:#edf2f7;--ink:#202b36;--muted:#526170;--line:#526170;--border:#8595a5;background:var(--bg);font-family:system-ui,sans-serif}
svg[data-theme=dark]{--bg:#1e1e1e;--panel:#252526;--head:#34383e;--ink:#eeeeee;--muted:#c1c8ce;--line:#c1c8ce;--border:#8595a5}
.erd-entity{fill:var(--panel);stroke:var(--border);stroke-width:1.4}.erd-header{fill:var(--head)}
.erd-divider{stroke:var(--border);stroke-width:.6}.erd-title{fill:var(--ink);font-size:15px;font-weight:650}
.erd-field{fill:var(--ink);font-size:13px}.erd-type,.erd-key{fill:var(--muted);font-size:12px}
.erd-relation{fill:none;stroke:var(--line);stroke-width:1.5}.erd-marker{stroke:var(--line);stroke-width:1.5;fill:none}
.erd-optional{fill:var(--bg)}.erd-label{fill:var(--ink);font-size:12px;paint-order:stroke;stroke:var(--bg);stroke-width:5px;stroke-linejoin:round}
""".strip()


def _object(value, required, optional, where):
    if not isinstance(value, dict):
        raise ValueError(f"{where} must be an object.")
    missing = set(required) - value.keys()
    unknown = value.keys() - set(required) - set(optional)
    if missing or unknown:
        raise ValueError(f"{where}: missing {sorted(missing)}, unknown {sorted(unknown)}.")


def _text(value, where):
    if not isinstance(value, str) or not value.strip() or any(unicodedata.category(c) in ("Cc", "Cs") for c in value):
        raise ValueError(f"{where} must be nonempty text without control characters.")


def _list(value, where):
    if not isinstance(value, list):
        raise ValueError(f"{where} must be an array.")


def validate(document: dict) -> dict:
    """Validate shape and graph references; do not infer keys/cardinality or mutate the source."""
    _object(document, ("schema_version", "diagram_type", "meta", "entities", "relationships"), ("layout",), "ERD")
    if type(document["schema_version"]) is not int or document["schema_version"] != 1 or document["diagram_type"] != "erd":
        raise ValueError("ERD requires schema_version: 1 and diagram_type: erd.")
    _object(document["meta"], ("title",), ("output",), "meta")
    for key, value in document["meta"].items():
        _text(value, f"meta.{key}")
    layout = document.get("layout", {})
    _object(layout, (), ("columns",), "layout")
    if "columns" in layout and (type(layout["columns"]) is not int or layout["columns"] < 1):
        raise ValueError("layout.columns must be a positive integer.")
    _list(document["entities"], "entities")
    if not document["entities"]:
        raise ValueError("entities must contain at least one entity.")
    entities = {}
    for index, entity in enumerate(document["entities"]):
        where = f"entities[{index}]"
        _object(entity, ("id", "attributes"), ("label",), where)
        _text(entity["id"], where + ".id")
        if entity["id"] in entities:
            raise ValueError(f"Duplicate entity id: {entity['id']}")
        if "label" in entity:
            _text(entity["label"], where + ".label")
        _list(entity["attributes"], where + ".attributes")
        names = set()
        for number, attribute in enumerate(entity["attributes"]):
            field = f"{where}.attributes[{number}]"
            _object(attribute, ("name", "type"), ("keys", "nullable"), field)
            for key in ("name", "type"):
                _text(attribute[key], field + "." + key)
            if attribute["name"] in names:
                raise ValueError(f"Duplicate attribute: {entity['id']}.{attribute['name']}")
            names.add(attribute["name"])
            keys = attribute.get("keys", [])
            _list(keys, field + ".keys")
            if any(not isinstance(key, str) or key not in ("PK", "FK", "UK") for key in keys) or len(set(keys)) != len(keys):
                raise ValueError(f"{field}.keys must contain unique PK, FK or UK values.")
            if "nullable" in attribute and type(attribute["nullable"]) is not bool:
                raise ValueError(f"{field}.nullable must be boolean.")
            if "PK" in keys and attribute.get("nullable") is True:
                raise ValueError(f"Primary key cannot be nullable: {entity['id']}.{attribute['name']}")
        entities[entity["id"]] = names
    _list(document["relationships"], "relationships")
    ids = set()
    for index, relation in enumerate(document["relationships"]):
        where = f"relationships[{index}]"
        _object(relation, ("from", "to", "from_cardinality", "to_cardinality"),
                ("id", "label", "from_attribute", "to_attribute", "identifying"), where)
        if "id" in relation:
            _text(relation["id"], where + ".id")
            if relation["id"] in ids:
                raise ValueError(f"Duplicate relationship id: {relation['id']}")
            ids.add(relation["id"])
        for side in ("from", "to"):
            _text(relation[side], where + "." + side)
            if relation[side] not in entities:
                raise ValueError(f"Unknown entity at {where}.{side}: {relation[side]}")
            if relation[side + "_cardinality"] not in CARDINALITIES:
                raise ValueError(f"{where}.{side}_cardinality must be one of {CARDINALITIES}.")
            if side + "_attribute" in relation:
                name = relation[side + "_attribute"]
                _text(name, where + "." + side + "_attribute")
                if name not in entities[relation[side]]:
                    raise ValueError(f"Unknown attribute: {relation[side]}.{name}")
        if "label" in relation:
            _text(relation["label"], where + ".label")
        if "identifying" in relation and type(relation["identifying"]) is not bool:
            raise ValueError(f"{where}.identifying must be boolean.")
    return {"ok": True, "renderer": "agent-factory-erd", "version": VERSION,
            "entities": len(entities), "relationships": len(document["relationships"])}


def _width(value):
    return sum(14 if unicodedata.east_asian_width(c) in ("W", "F") else 8 for c in value)


def _text_svg(x, y, value, css, extra=""):
    return f'<text x="{x}" y="{y}" class="{css}" {extra}>{escape(str(value))}</text>'


def _marker(x, y, angle, cardinality):
    many = cardinality.endswith("*")
    shape = '<path d="M0 -7 L12 0 L0 7 M0 0 H12"/>' if many else '<path d="M6 -7 V7"/>'
    shape += '<circle class="erd-optional" cx="21" cy="0" r="4"/>' if cardinality.startswith("0") else '<path d="M20 -7 V7"/>'
    return f'<g class="erd-marker" transform="translate({x} {y}) rotate({angle})">{shape}</g>'


def preview(document: dict) -> dict:
    validate(document)
    entities, relations = document["entities"], document["relationships"]
    columns = min(len(entities), document.get("layout", {}).get("columns", math.ceil(math.sqrt(len(entities)))))
    rows = math.ceil(len(entities) / columns)
    widths, heights, sizes = [0] * columns, [0] * rows, []
    for index, entity in enumerate(entities):
        attributes = entity["attributes"]
        name_width = max([_width(a["name"]) for a in attributes] + [40])
        type_width = max([_width(a["type"]) for a in attributes] + [40])
        width = max(260, _width(entity.get("label", entity["id"])) + 32, name_width + type_width + 190)
        height = 42 + max(1, len(attributes)) * 30
        widths[index % columns] = max(widths[index % columns], width)
        heights[index // columns] = max(heights[index // columns], height)
        sizes.append((width, height, name_width))
    # Reserve visible lanes for all authored relations rather than truncating large graphs.
    gap_x, gap_y, margin = 120 + 28 * len(relations), 100 + 28 * len(relations), 70 + 28 * len(relations)
    xs = [margin + sum(widths[:i]) + gap_x * i for i in range(columns)]
    ys = [margin + sum(heights[:i]) + gap_y * i for i in range(rows)]
    canvas_w = sum(widths) + gap_x * (columns - 1) + margin * 2
    canvas_h = sum(heights) + gap_y * (rows - 1) + margin * 2
    boxes, tables, edges = {}, [], []
    for index, (entity, (width, height, name_width)) in enumerate(zip(entities, sizes)):
        x, y = xs[index % columns], ys[index // columns]
        boxes[entity["id"]] = (x, y, width, height, index // columns, index % columns)
        table = [f'<g data-entity-index="{index}"><title>{escape(entity.get("label", entity["id"]))}</title>',
                 f'<rect class="erd-entity" x="{x}" y="{y}" width="{width}" height="{height}" rx="4"/>',
                 f'<path class="erd-header" d="M{x+1} {y+4} Q{x+1} {y+1} {x+4} {y+1} H{x+width-4} Q{x+width-1} {y+1} {x+width-1} {y+4} V{y+41} H{x+1} Z"/>',
                 _text_svg(x + 12, y + 27, entity.get("label", entity["id"]), "erd-title")]
        for number, attribute in enumerate(entity["attributes"]):
            baseline = y + 63 + number * 30
            table.append(f'<path class="erd-divider" d="M{x} {baseline-21} H{x+width}"/>')
            table.append(_text_svg(x + 10, baseline, ",".join(attribute.get("keys", [])), "erd-key"))
            table.append(_text_svg(x + 70, baseline, attribute["name"], "erd-field"))
            table.append(_text_svg(x + 86 + name_width, baseline, attribute["type"], "erd-type"))
            nullable = "NULL" if attribute.get("nullable") is True else "NOT NULL" if attribute.get("nullable") is False else ""
            table.append(_text_svg(x + width - 10, baseline, nullable, "erd-type", 'text-anchor="end"'))
        table.append('</g>')
        tables.append("".join(table))
    for index, relation in enumerate(relations):
        ax, ay, aw, ah, ar, ac = boxes[relation["from"]]
        bx, by, bw, bh, br, bc = boxes[relation["to"]]
        lane = 32 + index * 26
        def field_y(side, fallback):
            entity = next(e for e in entities if e["id"] == relation[side])
            if side + "_attribute" not in relation:
                return fallback
            number = next(i for i, a in enumerate(entity["attributes"]) if a["name"] == relation[side + "_attribute"])
            return boxes[relation[side]][1] + 57 + number * 30
        if relation["from"] == relation["to"]:
            x1, y1, x2, y2 = ax + aw, ay + 20, ax + aw, ay + ah - 15
            path = f'M{x1} {y1} H{x1+lane} V{y2} H{x2}'
            angles, label = (0, 0), (x1 + lane + 8, (y1 + y2) / 2)
        elif ar == br and abs(ac - bc) == 1:
            forward = ac < bc
            x1, x2 = (ax + aw, bx) if forward else (ax, bx + bw)
            y1, y2 = field_y("from", ay + ah / 2), field_y("to", by + bh / 2)
            mid = (x1 + x2) / 2 + index * 8
            path = f'M{x1} {y1} H{mid} V{y2} H{x2}'
            angles, label = ((0, 180) if forward else (180, 0)), (mid, min(y1, y2) - 18)
        elif ar == br:
            # Skipped columns use a lane above this row rather than crossing its other tables.
            x1, y1, x2, y2 = ax + aw / 2, ay, bx + bw / 2, by
            top = ay - lane
            path = f'M{x1} {y1} V{top} H{x2} V{y2}'
            angles, label = (270, 270), ((x1 + x2) / 2, top - 8)
        else:
            # Row gaps and an exterior lane avoid traversing unrelated entity boxes.
            forward = ar < br
            x1, x2 = ax + aw / 2, bx + bw / 2
            y1, y2 = (ay + ah, by) if forward else (ay, by + bh)
            first = ay + heights[ar] + lane if forward else ay - lane
            last = by - lane if forward else by + heights[br] + lane
            outside = canvas_w - margin + lane
            path = f'M{x1} {y1} V{first} H{outside} V{last} H{x2} V{y2}'
            angles, label = ((90, 270) if forward else (270, 90)), (outside - 8, (first + last) / 2)
        endpoints = [relation[side] + ("." + relation[side + "_attribute"] if side + "_attribute" in relation else "") for side in ("from", "to")]
        title = f"{endpoints[0]} {relation['from_cardinality']} — {relation['to_cardinality']} {endpoints[1]}"
        if relation.get("label"):
            title += ": " + relation["label"]
        dash = ' stroke-dasharray="6 4"' if relation.get("identifying") is False else ""
        edges.extend([f'<g data-relationship-index="{index}"><title>{escape(title)}</title>',
                      f'<path class="erd-relation" d="{path}"{dash}/>',
                      _marker(x1, y1, angles[0], relation["from_cardinality"]),
                      _marker(x2, y2, angles[1], relation["to_cardinality"]),
                      _text_svg(label[0], label[1], relation.get("label", ""), "erd-label", 'text-anchor="middle"'), '</g>'])
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_w} {canvas_h}" role="img" aria-labelledby="erd-title erd-desc">'
           f'<title id="erd-title">{escape(document["meta"]["title"])}</title>'
           f'<desc id="erd-desc">{len(entities)} entities; {len(relations)} relationships. PK: primary key; FK: foreign key; UK: unique key.</desc>'
           + "".join(edges + tables) + '</svg>')
    return {"ok": True, "title": document["meta"]["title"], "type": "erd", "svg": svg,
            "styles": STYLES, "renderer": "agent-factory-erd", "version": VERSION}


def html(document: dict) -> bytes:
    rendered = preview(document)
    svg = rendered["svg"].replace('role="img"', 'data-theme="light" role="img"', 1)
    return (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
            f'<title>{escape(rendered["title"])}</title><style>body{{margin:24px;font-family:system-ui}}svg{{max-width:100%;height:auto}}{STYLES}</style></head>'
            f'<body><h1>{escape(rendered["title"])}</h1>{svg}</body></html>').encode("utf-8")
