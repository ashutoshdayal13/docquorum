"""Conservative source-unit binding for explicit identifier queries.

Recognize 'of/for ... record ID' and 'whose key is ID' in field descriptions.
Only bind identifiers that actually occur in the complete original source.
Examples and date-format tokens do not create bindings. Unbound fields continue
to visit every source unit. This guards absence, not correctness of a value.
"""
import re

IDENTIFIER=re.compile(r'(?<![\w-])[A-Z][A-Z0-9]{1,11}(?:-[A-Z0-9]{2,24})+(?![\w-])')
QUERY_PREFIX=re.compile(r'(?:\b(?:of|for|from|with)\s+(?:the\s+)?'
    r'(?:order|invoice|record|account|document|entity|row|shipment)\s*'
    r'|\bwhose\s+[\w.-]+\s+(?:is|=)\s*)$',re.I)


def identifiers(text):
    return {m.group() for m in IDENTIFIER.finditer(text)}


def bindings(schema,source):
    known=identifiers(source)
    bound={}
    for field,node in schema.get('properties',{}).items():
        description=node.get('description','')
        hits={m.group() for m in IDENTIFIER.finditer(description)
              if m.group() in known and QUERY_PREFIX.search(description[:m.start()].rstrip(' \"\'`'))
              and not re.search(r'\bexample\b|\be\.g\.|\bsuch as\b',description[:m.start()],re.I)}
        if hits:bound[field]=hits
    return bound


def restrict(schema,source,bound):
    if not bound:return schema
    present=identifiers(source)
    active={k:v for k,v in schema.get('properties',{}).items()
            if k not in bound or bound[k]&present}
    out=dict(schema);out['properties']=active
    if 'required' in out:out['required']=[k for k in out['required'] if k in active]
    return out
