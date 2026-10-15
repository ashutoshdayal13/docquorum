"""
JSON-Schema helpers: find the lists a schema asks for, resolve references, size and split a
schema, and build the decoding schemas the readers send. No model and no annotation.
"""
import copy
import json


def defs_of(schema):
    return schema.get("$defs") or schema.get("definitions") or {}


def resolve(s, root, depth=0):
    """Follow $ref chains to the definition ({} when it cannot be resolved)."""
    while isinstance(s, dict) and "$ref" in s and depth < 20:
        s = defs_of(root).get(s["$ref"].split("/")[-1], {})
        depth += 1
    return s if isinstance(s, dict) else {}


def admits_null(s, root):
    s = resolve(s, root)
    t = s.get("type")
    if t == "null" or (isinstance(t, list) and "null" in t):
        return True
    return any(admits_null(alt, root) for comb in ("anyOf", "oneOf") for alt in s.get(comb) or [])


# ---------- the lists a schema asks for ----------
def is_array(node):
    """A list schema: "type": "array", a type list that includes it (a nullable list), or items."""
    t = node.get("type")
    return t == "array" or (isinstance(t, list) and "array" in t) or "items" in node


def find_array_field(schema):
    """The top-level list with the widest records: (name, item schema, description)."""
    defs = defs_of(schema)

    def res(node, depth=0):
        if depth > 6 or not isinstance(node, dict):
            return node
        if "$ref" in node:
            return res(defs.get(node["$ref"].split("/")[-1], {}), depth + 1)
        for comb in ("anyOf", "oneOf", "allOf"):
            if comb in node:
                for opt in node[comb]:
                    r = res(opt, depth + 1)
                    if isinstance(r, dict) and is_array(r):
                        return r
                return res(node[comb][0], depth + 1)
        return node

    arrays = []
    for name, prop in (schema.get("properties") or {}).items():
        r = res(prop)
        if isinstance(r, dict) and is_array(r):
            item = res(r.get("items") or {})
            arrays.append((name, item, prop.get("description") or r.get("description") or ""))
    if not arrays:
        return None
    arrays.sort(key=lambda a: -len((a[1].get("properties") or {})))
    return arrays[0]


def find_all_arrays(schema):
    """Every top-level list, widest records first."""
    defs = defs_of(schema)
    out = [a for name, prop in (schema.get("properties") or {}).items()
           if (a := find_array_field({"properties": {name: prop}, "$defs": defs}))]
    out.sort(key=lambda a: -len((a[1].get("properties") or {})))
    return out


def scalar_fields(schema):
    """The top-level properties that are not lists."""
    names = {a[0] for a in find_all_arrays(schema)}
    return {k: v for k, v in (schema.get("properties") or {}).items() if k not in names}


def without_fields(schema, names):
    """The schema minus the named top-level properties (None when nothing is left)."""
    props = {k: v for k, v in (schema.get("properties") or {}).items() if k not in names}
    if not props:
        return None
    rest = dict(schema, properties=props)
    if isinstance(schema.get("required"), list):
        rest["required"] = [k for k in schema["required"] if k in props]
    return rest


# ---------- size and split ----------
def compact(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def leaf_count(node, defs, depth=0):
    """Number of leaf fields (a list counts its item's leaves once)."""
    if depth > 8 or not isinstance(node, dict):
        return 1
    if "$ref" in node:
        return leaf_count(defs.get(node["$ref"].split("/")[-1], {}), defs, depth + 1)
    for comb in ("anyOf", "oneOf", "allOf"):
        if comb in node:
            return max(leaf_count(o, defs, depth + 1) for o in node[comb])
    if node.get("type") == "object" or "properties" in node:
        return sum(leaf_count(v, defs, depth + 1) for v in (node.get("properties") or {}).values()) or 1
    return 1


def _refs(node, out):
    if isinstance(node, dict):
        r = node.get("$ref")
        if isinstance(r, str):
            out.add(r.split("/")[-1])
        for v in node.values():
            _refs(v, out)
    elif isinstance(node, list):
        for v in node:
            _refs(v, out)


def _closure(names, defs):
    """Definitions reachable from `names`, transitively."""
    seen, todo = set(), list(names)
    while todo:
        n = todo.pop()
        if n in seen or n not in defs:
            continue
        seen.add(n)
        more = set()
        _refs(defs[n], more)
        todo.extend(more - seen)
    return seen


def schema_groups(schema, budget_chars):
    """The schema split into groups of top-level fields, each (with the definitions it
    references) at most budget_chars long."""
    props = schema.get("properties") or {}
    dkey = "$defs" if "$defs" in schema else ("definitions" if "definitions" in schema else None)
    defs = schema.get(dkey) or {} if dkey else {}

    def build(keys):
        sub = {"type": "object", "properties": {k: props[k] for k in keys}}
        if schema.get("description"):
            sub["description"] = schema["description"]
        if schema.get("required"):
            req = [k for k in schema["required"] if k in keys]
            if req:
                sub["required"] = req
        need = set()
        _refs(sub["properties"], need)
        need = _closure(need, defs)
        if need and dkey:        # in the schema's own order (a set's order varies between runs)
            sub[dkey] = {n: d for n, d in defs.items() if n in need}
        return sub

    groups, cur = [], []
    for k in props:
        trial = cur + [k]
        if cur and len(compact(build(trial))) > budget_chars:
            groups.append(build(cur))
            cur = [k]
        else:
            cur = trial
    if cur:
        groups.append(build(cur))
    return groups


# ---------- decoding schemas ----------
def array_schema(item, root=None, **bounds):
    """A decoding schema for a list of items, with the definitions hoisted to the root (a
    "$ref": "#/$defs/X" resolves from the root)."""
    items = {k: v for k, v in item.items() if k not in ("$defs", "definitions")}
    out = {"type": "array", **bounds, "items": items}
    src = root or item
    for key in ("$defs", "definitions"):
        if src.get(key):
            out[key] = src[key]
    return out


def _nullable(node):
    t = node.get("type")
    if "enum" in node and None not in node["enum"]:
        node["enum"] = list(node["enum"]) + [None]
    if "oneOf" in node and "anyOf" not in node:
        node["anyOf"] = node.pop("oneOf")
    if "anyOf" in node:
        if not any(isinstance(a, dict) and a.get("type") == "null" for a in node["anyOf"]):
            node["anyOf"] = list(node["anyOf"]) + [{"type": "null"}]
    elif isinstance(t, list):
        if "null" not in t:
            node["type"] = t + ["null"]
    elif isinstance(t, str) and t != "null":
        node["type"] = [t, "null"]
    elif "$ref" in node:
        node["anyOf"] = [{"$ref": node.pop("$ref")}, {"type": "null"}]


def require_all(schema):
    """The schema with every object property required; each added requirement nullable."""
    s = copy.deepcopy(schema)

    def walk(node):
        if isinstance(node, dict):
            props = node.get("properties")
            if isinstance(props, dict) and props:
                had = set(node.get("required") or [])
                for k, v in props.items():
                    if k not in had and isinstance(v, dict):
                        _nullable(v)
                node["required"] = list(props.keys())
            for v in list(node.values()):
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(s)
    return s


def missing_keys(schema, obj):
    """How many schema properties the output leaves out (in objects and list items)."""
    defs = defs_of(schema)

    def res(s, depth=0):
        while isinstance(s, dict) and "$ref" in s and depth < 20:
            s = defs.get(s["$ref"].split("/")[-1], {})
            depth += 1
        if isinstance(s, dict) and "anyOf" in s:
            for a in s["anyOf"]:
                a = res(a, depth + 1)
                if isinstance(a, dict) and ("properties" in a or "items" in a):
                    return a
        return s

    def walk(s, o):
        s = res(s)
        if not isinstance(s, dict):
            return 0
        if isinstance(o, dict) and isinstance(s.get("properties"), dict):
            return sum(1 if k not in o else walk(v, o[k]) for k, v in s["properties"].items())
        if isinstance(o, list) and isinstance(s.get("items"), dict):
            return sum(walk(s["items"], x) for x in o)
        return 0
    return walk(schema, obj)


# ---------- JSON templates (UNIKIE style) ----------
JSON_TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}


def _schema_like(obj):
    """Whether a dict uses JSON-Schema keywords as keywords. A template may have a field named
    "type" or "properties"; there its value is an empty leaf (or a template), not a JSON type."""
    t = obj.get("type")
    props = obj.get("properties")
    return ("$schema" in obj or (isinstance(t, str) and t in JSON_TYPES)
            or (isinstance(t, list) and bool(t) and set(t) <= JSON_TYPES)
            or (isinstance(props, dict) and props == {} and "type" in obj)
            or (isinstance(props, dict) and bool(props)
                and all(isinstance(v, dict) and (not v or _schema_like(v) or "$ref" in v or "description" in v)
                        for v in props.values())))


def is_template(obj):
    """A JSON template: only empty leaves, and no JSON-Schema keywords used as keywords."""
    if isinstance(obj, dict):
        if _schema_like(obj):
            return False
        return all(is_template(v) for v in obj.values())
    if isinstance(obj, list):
        return all(is_template(v) for v in obj)
    return obj in ("", None)


def template_to_schema(t):
    if isinstance(t, dict):
        return {"type": "object", "additionalProperties": False,
                "properties": {k: template_to_schema(v) for k, v in t.items()}}
    if isinstance(t, list):
        return {"type": "array", "items": template_to_schema(t[0] if t else "")}
    return {"type": ["string", "null"]}


def fill_template(pred, t):
    if isinstance(t, dict):
        pred = pred if isinstance(pred, dict) else {}
        return {k: fill_template(pred.get(k), v) for k, v in t.items()}
    if isinstance(t, list):
        return [fill_template(x, t[0] if t else "") for x in pred] if isinstance(pred, list) else []
    return "" if pred is None or isinstance(pred, (dict, list)) else str(pred)
