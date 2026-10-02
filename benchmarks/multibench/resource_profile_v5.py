"""V4 plus bounded image recovery with disjoint ownership of source bands.

The original page is tried first. On truncation/overflow, read smaller bands with
context above and below. A red left marker identifies the owned body; the model
must emit a record only where its first line is owned. Printed duplicate records
are retained. This is a policy to measure, not proof of complete visual recall.
"""
import base64
import io

from PIL import Image, ImageDraw

from resource_profile_v4 import install as install_v4

MAX_DEPTH = 6
MIN_BAND_HEIGHT = 128


def decode_image(encoded):
    return Image.open(io.BytesIO(base64.b64decode(encoded))).convert('RGB')


def seam(image, first, last):
    """Prefer a low-ink horizontal gutter near the middle, without using labels."""
    middle = (first+last)//2
    radius = min((last-first)//10, 80)
    gray = image.convert('L').resize((min(image.width,256),image.height))
    pixels = gray.load()
    candidates = range(max(first+MIN_BAND_HEIGHT,middle-radius),
                       min(last-MIN_BAND_HEIGHT,middle+radius)+1)
    if not candidates: return middle
    # Three scanlines keep a single white antialiasing line from winning.
    def ink(y):
        dark = sum(pixels[x,yy]<220 for yy in range(max(first,y-1),min(last,y+2))
                   for x in range(gray.width))
        return dark,abs(y-middle),y
    return min(candidates,key=ink)


def band_image(image, first, last):
    """Attach header/edge context while marking exactly [first,last) as owned."""
    context = min(64,max(8,(last-first)//8))
    lo,hi = max(0,first-context),min(image.height,last+context)
    header_height = min(160,image.height//10) if first>=160 else 0
    offset = header_height+24 if header_height else 0
    canvas = Image.new('RGB',(image.width+12,hi-lo+offset),'white')
    if header_height:
        canvas.paste(image.crop((0,0,image.width,header_height)),(12,0))
        ImageDraw.Draw(canvas).text((12,header_height+4),'HEADER CONTEXT ONLY',fill='black')
    canvas.paste(image.crop((0,lo,image.width,hi)),(12,offset))
    ImageDraw.Draw(canvas).rectangle((0,offset+first-lo,7,offset+last-lo-1),fill='red')
    buf=io.BytesIO();canvas.save(buf,format='JPEG',quality=95)
    return base64.b64encode(buf.getvalue()).decode()


def install():
    from docquorum.agents import reader
    profile=install_v4()
    original=reader._ask_chunk

    def recoverable(error):
        return ((isinstance(error,RuntimeError) and 'Image record partition incomplete:' in str(error))
                or (isinstance(error,ValueError) and 'Input needs partitioning:' in str(error)))

    def read_band(cl,image,first,last,meta,label,depth,stat):
        name,lead,item,grammar=meta
        ownership = ('\nThis image contains a BODY band with a RED MARKER along its left edge. '
            'Other pixels, including any HEADER CONTEXT ONLY strip, are context, not additional rows. '
            'Return a record only if its FIRST printed line is aligned with the red marker. '
            'Use context to complete that record; never extract a record that begins outside the marker. '
            'Repeated printed records within the marker remain separate entries.\n')
        local=(name,lead+ownership,item,grammar)
        try:
            return original(cl,reader.NO_TEXT,(band_image(image,first,last),),local,
                            f'{label} body y={first}:{last}/{image.height}',stat)[0]
        except Exception as error:
            if not recoverable(error):raise
            if depth>=MAX_DEPTH or last-first<2*MIN_BAND_HEIGHT:
                raise RuntimeError(f'Image recovery could not complete: {label}/{first}:{last}') from error
        cut=seam(image,first,last)
        with stat['lock']:stat['refined']+=1
        return (read_band(cl,image,first,cut,meta,label,depth+1,stat)
                +read_band(cl,image,cut,last,meta,label,depth+1,stat))

    def ask_chunk(cl,text,imgs,meta,label,stat):
        if text==reader.NO_TEXT and not imgs:
            raise RuntimeError(f'Image source missing: {label}')
        try:
            return original(cl,text,imgs,meta,label,stat)
        except Exception as error:
            if not imgs or not recoverable(error):raise
            if len(imgs)!=1:raise RuntimeError('Image recovery requires one physical page') from error
        image=decode_image(imgs[0])
        if image.height<2*MIN_BAND_HEIGHT:raise RuntimeError(f'Image source too small to recover: {label}')
        cut=seam(image,0,image.height)
        with stat['lock']:stat['refined']+=1
        rows=(read_band(cl,image,0,cut,meta,label,1,stat)
              +read_band(cl,image,cut,image.height,meta,label,1,stat))
        return rows,False

    reader._ask_chunk=ask_chunk
    return profile|{'profile':'DocQuorum8B-bounded-v5',
        'image_overflow_recovery':'Recursively split owned horizontal bands; header/edge context is not owned',
        'image_recovery_depth':MAX_DEPTH,'image_min_band_height_px':MIN_BAND_HEIGHT,
        'native_overflow':'Complete structural XML elements or complete text lines; never clip source',
        'development_scope':'V4 truncation failures and original oversized native XML input; selected checks are development'}
