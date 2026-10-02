"""Complete, bounded native-source reading for the V5 experiment.

Partition XML at complete element boundaries and retain ancestral tags. Text is
split on lines with their original separators. All partitions must finish before
merging; a failed partition never becomes an empty successful reading.
"""
import copy
import json
import xml.etree.ElementTree as ET

from docquorum import config as C
from docquorum.agents import prompts
from resource_profile_v3 import merge_windows

TARGET_CHARS=18000
MAX_DEPTH=12


def xml_parts(text,budget=TARGET_CHARS):
    root=ET.fromstring(text)
    def serialize(node):return ET.tostring(node,encoding='unicode')
    def partition(node):
        source=serialize(node)
        if len(source)<=budget:return [source]
        if not len(node):raise ValueError('One XML leaf exceeds the structural partition budget')
        shell=copy.copy(node);shell[:]=[]
        overhead=len(serialize(shell))
        if overhead>=budget:raise ValueError('XML ancestor text exceeds the structural partition budget')
        children=[]
        for child in node:
            children.extend(partition(child))
        groups=[];current=[];size=overhead
        for child in children:
            if current and size+len(child)>budget:
                groups.append(current);current=[];size=overhead
            current.append(child);size+=len(child)
        if current:groups.append(current)
        out=[]
        for index,group in enumerate(groups):
            part=copy.copy(shell)
            # Preserve ancestor text/tail once, rather than creating extra data
            # by repeating it in every source partition.
            if index:part.text=None
            if index<len(groups)-1:part.tail=None
            # Tails are whitespace in many exports but can also be data. Parse
            # children in a wrapper so a non-whitespace tail remains attached.
            for child in group:
                wrapped=ET.fromstring('<partition>'+child+'</partition>')
                part.extend(list(wrapped))
            out.append(serialize(part))
        return out
    return partition(root)


def text_parts(text,budget=TARGET_CHARS):
    parts=[];current=[];size=0
    for line in text.splitlines(keepends=True):
        if len(line)>budget:raise ValueError('A native source line exceeds the partition budget')
        if current and size+len(line)>budget:
            parts.append(''.join(current));current=[];size=0
        current.append(line);size+=len(line)
    if current:parts.append(''.join(current))
    return parts


def read(cl,text,schema,task,extension,bind_queries=False):
    from query_scope import bindings,restrict
    calls_before=len(cl.calls)
    bound=bindings(schema,text) if bind_queries else {}
    def request(source,label):
        effective=restrict(schema,source,bound)
        if bound and not effective.get('properties'):return {}
        prompt=prompts.WHOLE.format(rules='',task=f'TASK\n{task or ""}\n\n',n=1,
            modality=f'This is {label} of the native {extension} source. Fill only fields shown here; use null for absent fields.',
            text_block=prompts.TEXT_LAYER.format(body=source),schema=json.dumps(effective,indent=1))
        response=cl.chat.completions.create(model=C.MODEL,temperature=0,max_tokens=8192,
            response_format={'type':'json_object'},extra_body={'chat_template_kwargs':{'enable_thinking':False}},
            messages=[{'role':'user','content':prompt}])
        choice=response.choices[0]
        if choice.finish_reason!='stop':raise RuntimeError('Native-format response was truncated')
        got=json.loads(choice.message.content)
        if not isinstance(got,dict):raise ValueError('Expected a JSON object')
        return {k:v for k,v in got.items() if k in effective['properties']} if bound else got
    def incomplete(error):
        return (isinstance(error,ValueError) and 'Input needs partitioning:' in str(error)
                or isinstance(error,RuntimeError) and 'Native-format response was truncated' in str(error))
    try:
        got=request(text,'the complete original source')
        return got,{'readings':['native_text'],'native_format':extension,'requests':cl.calls[calls_before:]}
    except Exception as error:
        if not incomplete(error):raise
    splitter=xml_parts if extension=='.xml' else text_parts
    partitions=splitter(text)
    if not partitions:raise ValueError('Cannot partition empty native source')
    assigned={field:[i+1 for i,part in enumerate(partitions) if field in restrict(schema,part,bound).get('properties',{})]
              for field in schema.get('properties',{})}
    if any(not units for units in assigned.values()):
        raise RuntimeError('A supplied schema field has no source-unit assignment')
    def complete(source,label,depth):
        try:return request(source,label)
        except Exception as error:
            if not incomplete(error):raise
            if depth>=MAX_DEPTH:raise RuntimeError('Native partition did not complete') from error
        smaller=splitter(source,max(256,len(source)//2))
        if len(smaller)<2:raise RuntimeError('Native source cannot be further partitioned')
        merged={}
        for i,part in enumerate(smaller):
            merged=merge_windows(merged,complete(part,f'{label}.{i+1}',depth+1))
        return merged
    result={}
    for i,part in enumerate(partitions):
        result=merge_windows(result,complete(part,f'partition {i+1}/{len(partitions)}',0))
    return result,{'readings':['native_partitions'],'native_format':extension,
        'source_partitions':len(partitions),'all_partitions_completed':True,'requests':cl.calls[calls_before:],
        'query_binding_fields':sorted(bound),'field_window_assignments':assigned,
        'every_field_scheduled':all(assigned.values())}
