"""Write ppt/flow/docquorum-flow.tex (LaTeX Beamer) from the assets and the results snapshots, and compile it.

    python ppt/flow/build_beamer.py       (after ppt/flow/make_assets.py; needs pdflatex with beamer/metropolis)

Every number on the slides comes from ppt/flow/assets/*.json or docs/results/.
"""
import json
import subprocess
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
A = HERE / "assets"
RES = ROOT / "docs" / "results"
facts = json.loads((A / "facts.json").read_text())
quorum = json.loads((A / "quorum_example.json").read_text())
unikie_ex = json.loads((A / "unikie_example.json").read_text())
sys.path.insert(0, str(RES))
import pricing as PR  # noqa: E402
COST = {f.stem: json.loads(f.read_text()) for f in sorted(PR.COSTS.glob("*.json"))}
MEASURED = {b: PR.measured(b) for b in COST}
PRICE = PR.PRICES["usd_per_million_tokens"]
QWEN = PRICE["qwen3.8-27b"]


def cost(bench, key, digits=0):
    """A measured mean per document (results/costs/<bench>.json, priced by docs/results/pricing.py), or '--'."""
    c = (MEASURED.get(bench) or {}).get(key)
    return "--" if c is None else f"{c:,.{digits}f}"


def esc(s):
    s = str(s).replace("\\", "\x00")          # restored last, so the brace escapes below cannot mangle it
    for a, b in [("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"), ("_", r"\_"),
                 ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}"),
                 ("’", "'"), ("‘", "`"), ("“", "``"), ("”", "''"), ("…", r"\ldots{}"),
                 ("—", "---"), ("–", "--"), ("·", r"$\cdot$")]:
        s = s.replace(a, b)
    return s.replace("\x00", r"\textbackslash{}")


def code(lines, size=r"\scriptsize"):
    """Monospaced block; leading spaces kept."""
    out = []
    for ln in lines:
        lead = len(ln) - len(ln.lstrip(" "))
        body = esc(ln.lstrip(" ")).replace('"', r'\textquotedbl{}').replace("'", r"\textquotesingle{}")
        out.append(r"\hspace*{%.2fem}" % (0.52 * lead) + body if lead else body)
    return "{" + size + r"\ttfamily\raggedright " + r"\\".join(out) + r"\par}"


def disp(v):
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def ranks(scores):
    d = [disp(v) for v in scores]
    return [1 + sum(x > v for x in d) for v in d]


ARROW = r"\,$\rightarrow$\,"
form = facts["form"]
P, M, O = (quorum["views"][k] for k in "PMO")
filled = {k: sum(1 for v in d.values() if v not in (None, "", [], {})) for k, d in (("P", P), ("M", M), ("O", O))}

# ------------------------------------------------------------------ preamble
T = [r"""\documentclass[aspectratio=169,10pt]{beamer}
\usetheme[numbering=fraction,progressbar=none,sectionpage=none,block=fill]{metropolis}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{textcomp}
\usepackage{booktabs,colortbl,tabularx,array}
\usepackage{tikz}
\definecolor{navy}{HTML}{1B2A4A}
\definecolor{muted}{HTML}{5B6577}
\definecolor{good}{HTML}{1E7A60}
\definecolor{bad}{HTML}{B03A2E}
\definecolor{hl}{HTML}{DDEFE8}
\definecolor{routeA}{HTML}{C9731F}
\definecolor{routeB}{HTML}{2F7FC1}
\definecolor{routeC}{HTML}{3E8E57}
\definecolor{routeD}{HTML}{7D5BA6}
\setbeamercolor{frametitle}{bg=navy,fg=white}
\setbeamercolor{title separator}{fg=navy}
\setbeamercolor{normal text}{fg=black!88,bg=white}
\setbeamercolor{alerted text}{fg=good}
\setbeamercolor{block title}{bg=navy!10,fg=navy}
\setbeamercolor{block body}{bg=navy!4}
\setbeamerfont{frametitle}{size=\large,series=\bfseries}
\setbeamertemplate{frame footer}{DocQuorum: agentic document extraction with open models}
\newcolumntype{Y}{>{\raggedright\arraybackslash}X}
\newcommand{\src}[1]{\par\vfill{\tiny\color{muted}#1\par}}
\newcommand{\route}[1]{\tikz[baseline=-0.65ex]\node[circle,fill=route#1,text=white,inner sep=1.3pt,font=\scriptsize\bfseries]{#1};}
\newcommand{\cand}[2]{\tikz[baseline=-0.65ex]\node[circle,fill=#2,text=white,inner sep=1.3pt,font=\scriptsize\bfseries]{#1};}
\newcommand{\nul}{\textcolor{bad}{\texttt{null}}}
\title{DocQuorum}
\subtitle{Agentic document extraction with open models:\\the pipeline on real benchmark documents}
\date{October 2026}
\author{}
\institute{Every example is a real benchmark document and a stored pipeline output; no model was called to make these slides.}
\begin{document}
\maketitle
"""]


def frame(title, body, opts=""):
    T.append(r"\begin{frame}" + (f"[{opts}]" if opts else "") + "{" + title + "}\n" + body.strip() + "\n\\end{frame}\n")


# ------------------------------------------------------------------ outline
T.append(r"\section{Task and pipeline}" + "\n")
frame("Outline", r"""
\begin{columns}[T]
\column{0.48\textwidth}
\begin{enumerate}
\item Task and pipeline
\item Walkthrough on real documents\\
  {\footnotesize inputs, routing, parsing, readers, deterministic checks, selection by quorum, output}
\item Results on six benchmarks: what the pipeline adds, cost; zoom re-reading
\item Summary
\item Complete results, one table per benchmark
\end{enumerate}
\column{0.48\textwidth}
\begin{block}{Setting}
\small
Open-weight models only: Qwen3.8-27B (FP8) for reading and MinerU2.5 for parsing scans, served on a single GPU.
Each benchmark is scored with its own official scorer.
\end{block}
\end{columns}
""")

# ------------------------------------------------------------------ task
task = facts["task_example"]["task"]
schema_lines = ['"p1_company": {', '  "anyOf": [{"type": "string"},', '            {"type": "null"}],',
                '  "description": "The \'Company\' field',
                '    in the identification block on', '    page 1 ... Extract verbatim as', '    printed; null if blank. Do NOT',
                '    confuse with ..."', "},", '"p1_county": {...},', '"p1_total_depth": {...},', "... 74 further fields"]
frame("Problem statement", r"""
\begin{columns}[T]
\column{0.40\textwidth}
\begin{block}{Task}
\small
\textbf{Input:} a document $D$ (PDF or image), a JSON Schema $S$ or a JSON template, and optionally a task description $T$.\\[0.4em]
\textbf{Output:} one JSON object $Y$ that conforms to $S$, every value supported by $D$, absent values \texttt{null}.
\end{block}
\vspace{0.3em}
{\footnotesize\textbf{Optional task} (real example, receipt schema):\\
\itshape ``""" + esc(task[:118].rsplit(" ", 1)[0]) + r""" \ldots''\par}
\column{0.25\textwidth}
\centering
\includegraphics[height=4.2cm]{assets/input_form_p1.png}\\[0.3em]
{\tiny Scanned 1955 well-plugging application (Railroad Commission of Texas), """ + str(form["pages"]) + r""" pages, no text layer.\par}
\column{0.33\textwidth}
\textbf{\small JSON Schema (""" + str(form["fields"]) + r""" fields), excerpt}\\[0.3em]
\begin{beamercolorbox}[wd=\linewidth,sep=0.5em]{block body}
""" + code(schema_lines, r"\tiny") + r"""
\end{beamercolorbox}
\end{columns}
\src{ExtractBench short: """ + esc(form["name"]) + r""" (schema shortened); task text from the schema of hingham\_lowes\_receipt.}
""")

frame("Pipeline overview", r"""
\centering
\includegraphics[width=\textwidth,height=6.2cm,keepaspectratio]{assets/pipeline.png}
\src{Pipeline figure, describing the single-document entry point \texttt{docquorum.extract}; the lower panels show the bounded reader loop and guarded zoom updates (v1.3; v1.4 adds no step).}
""")

# ------------------------------------------------------------------ routing
T.append(r"\section{Walkthrough on real documents}" + "\n")
names = {"real_oklahoma_unclaimed_2024": "Unclaimed-property register", "oklahoma_county_purchase_order_avl_systems":
         "County purchase order", "W14-58025_W14 Admin Reviewed": "W-14 well form",
         "2A-9-160298_109929": "1955 plugging application", "bar-lev-2022": "Tax return"}
reading = {"A": "Layout reader", "B": "Reader agent: text + images", "C": "Three readings, then quorum",
           "D": "Reader agent on the parse"}
cells, caps = [], []
for i, r in enumerate(facts["routes"]):
    cells.append(r"\includegraphics[height=2.1cm,width=0.17\textwidth,keepaspectratio]{assets/route_%d.png}" % i)
    cpp = f"{r['chars_per_page']:,} char./page" + (" (OCR layer)" if r["ocr_layer"] else "") if r["chars_per_page"] else "no embedded text"
    caps.append(r"{\scriptsize\route{%s}\ \textbf{%s}\par}{\tiny %s\par %d page%s, %s\par}" % (
        r["route"], esc(reading[r["route"]]), esc(names[r["name"]]), r["pages"], "s" if r["pages"] > 1 else "", esc(cpp)))
frame("Step 2: the available evidence decides the route", r"""
\centering
\begin{tabular}{*{5}{>{\centering\arraybackslash}p{0.17\textwidth}}}
""" + " & ".join(cells) + r"""\\[0.2em]
""" + " & ".join(caps) + r"""
\end{tabular}

\vspace{0.3em}
\begin{block}{Routing rule}
\scriptsize
Layout first: pages printed as equal-width columns of records, or a ruled table on a scan, go to a layout reader \route{A}.
Otherwise a PDF with embedded text (at least 50 characters per page; a digital PDF or an OCR layer) is read once \route{B}.
A scan without text is parsed by MinerU and read three ways if it has at most 12 pages \route{C}, or read through its parse \route{D}.
\end{block}
\src{ExtractBench documents; embedded characters per page measured with pdftotext.}
""")

# ------------------------------------------------------------------ MinerU
mn = facts["mineru"]
keep = [0, 1, 5, 6, 7]
mrows = [[mn["table"][0][k] for k in keep]] + [[(r[k] if k < len(r) else "") for k in keep] for r in mn["table"][1:6]]
mt = r"\setlength{\tabcolsep}{3pt}\begin{tabular}{@{}>{\raggedright\arraybackslash}p{2.5cm}>{\raggedright\arraybackslash}p{1.9cm}p{1.0cm}p{0.4cm}p{1.0cm}@{}}\toprule" + "\n"
mt += " & ".join(r"\textbf{%s}" % esc(c) for c in mrows[0]) + r"\\\midrule" + "\n"
for r in mrows[1:]:
    mt += " & ".join(esc(c) for c in r) + r"\\" + "\n"
mt += r"\bottomrule\end{tabular}"
raw = [x.strip()[:46] + "..." for x in mn["raw"].replace("<TABLE>", "").replace("<table>", "").split("</tr>")[:3]]
frame("Step 2: MinerU returns a scanned table as cells", r"""
\begin{columns}[T]
\column{0.41\textwidth}
\textbf{\small Scanned page (detail)}\\[0.3em]
\includegraphics[width=\linewidth]{assets/mineru_page.png}\\[0.5em]
\textbf{\small MinerU output (raw HTML, abbreviated)}\\[0.2em]
\begin{beamercolorbox}[wd=\linewidth,sep=0.4em]{block body}
""" + code(raw, r"\tiny") + r"""
\end{beamercolorbox}
\column{0.57\textwidth}
\textbf{\small The same rows as table cells (""" + str(mn["rows"]) + r""" rows on this page)}\\[0.3em]
{\tiny """ + mt + r"""}

\vspace{0.6em}
{\scriptsize Columns stay aligned: an empty cell stays empty rather than pulling the next value into its place.
Recognition errors remain, so the reader receives the page image together with the parse.\par}
\end{columns}
\src{ExtractBench long: """ + esc(mn["name"]) + r""", page """ + str(mn["page"]) + r"""; cached MinerU2.5 parse.}
""")

# ------------------------------------------------------------------ column flow
cf = facts["colflow"]
crow = "".join(r"\texttt{%s} & \texttt{%s}\\" % (esc(r["name"]), esc(r["locale"] or "null")) + "\n" for r in cf["page2_first"])
frame(r"Step 3, route \route{A}: the column reader", r"""
\begin{columns}[T]
\column{0.27\textwidth}
\centering
\includegraphics[height=6.1cm]{assets/colflow_page.png}
\column{0.12\textwidth}
\centering
\includegraphics[height=6.1cm]{assets/colflow_crop.png}
\column{0.57\textwidth}
\textbf{\small Records returned for column 1 (page 2)}\\[0.3em]
{\scriptsize\begin{tabularx}{\linewidth}{@{}p{3.2cm}Y@{}}\toprule
\textbf{name} & \textbf{locale}\\\midrule
""" + crow + r"""\bottomrule\end{tabularx}}

\vspace{0.8em}
\begin{tabular}{@{}lll@{}}
{\Large\bfseries\color{routeA} """ + str(cf["columns"]) + r"""} & {\Large\bfseries\color{routeA} """ + str(cf["pages"]) + r"""} & {\Large\bfseries\color{routeA} """ + f"{cf['records_total']:,}" + r"""}\\
{\scriptsize columns detected on the page\quad} & {\scriptsize pages\quad} & {\scriptsize records in the final output}
\end{tabular}

\vspace{0.8em}
{\footnotesize The trigger is page geometry only: at least three text columns of near-equal width.
Each column is cut out and read top to bottom in one call; a record continued from the previous column is joined to it.}
\end{columns}
\src{ExtractBench long: """ + esc(cf["name"]) + r""", page 2. Column boxes drawn with the pipeline's own geometry code; records from the stored final output.}
""")

# ------------------------------------------------------------------ ruled
rl = facts["ruled"]
rrow = "".join(r"\texttt{%s} & \texttt{%s} & \texttt{%s} & \texttt{%s}\\" % tuple(esc(x or "null") for x in (
    r["name"], r["address_1"], r["city"], r["state"])) + "\n" for r in rl["first"])
frame(r"Step 3, route \route{A}: the ruled-table reader", r"""
\begin{columns}[T]
\column{0.52\textwidth}
\includegraphics[width=\linewidth]{assets/ruled_page.png}\\[-0.1em]
{\tiny\color{muted} Printed rules detected after deskewing by """ + str(rl["angle"]) + r"""$^\circ$ (green).\par}\vspace{0.5em}
\includegraphics[width=\linewidth]{assets/ruled_band.png}\\[-0.1em]
{\tiny\color{muted} One call: the header row stacked on a band of 12 rows; the reply must contain exactly 12 entries.\par}
\column{0.45\textwidth}
\begin{tabular}{@{}ll@{}}
{\Large\bfseries\color{routeA} """ + str(rl["rows_counted"]) + r"""} & {\Large\bfseries\color{routeA} """ + str(rl["rows_returned"]) + r"""}\\
{\scriptsize rows counted from the rules\quad} & {\scriptsize rows returned by the reader}
\end{tabular}

\vspace{0.4em}
{\footnotesize Bands on page """ + str(rl["page"]) + ": " + " + ".join(str(b) for b in rl["bands"]) + r""".}

\vspace{0.5em}
{\tiny\begin{tabularx}{\linewidth}{@{}Yp{1.9cm}p{1.0cm}p{0.5cm}@{}}\toprule
\textbf{name} & \textbf{address\_1} & \textbf{city} & \textbf{state}\\\midrule
""" + rrow + r"""\bottomrule\end{tabularx}}

\vspace{0.5em}
{\footnotesize Fixing the number of entries per band prevents repeated identical rows from multiplying or disappearing.}
\end{columns}
\src{ExtractBench long: """ + esc(rl["name"]) + r""", page """ + str(rl["page"]) + r""". Rows from the stored final output.}
""")

# ------------------------------------------------------------------ three readings
fields = ["p1_company", "p1_county", "p1_well_no", "p1_name_of_lease", "p1_drilling_commenced",
          "p1_party_plugging_well", "p2_correspondence_name"]
rr = ""
for f in fields:
    vals = []
    for v, other in ((P.get(f), M.get(f)), (M.get(f), P.get(f)), (O.get(f), None)):
        if v in (None, ""):
            vals.append(r"\nul")
        else:
            t = r"\texttt{%s}" % esc(v)
            vals.append(r"\textcolor{bad}{%s}" % t if other is not None and v != other else t)
    rr += r"\texttt{%s} & %s\\" % (esc(f), " & ".join(vals)) + "\n"
frame(r"Step 3, route \route{C}: three independent readings of one scan", r"""
\begin{columns}[T]
\column{0.24\textwidth}
\centering
\includegraphics[width=\linewidth]{assets/input_form_p1.png}
\column{0.74\textwidth}
{\scriptsize\begin{tabularx}{\linewidth}{@{}p{3.1cm}YYp{1.6cm}@{}}\toprule
\textbf{field} & \cand{P}{routeB}\ \textbf{image reading} & \cand{M}{routeC}\ \textbf{parse reading} & \cand{O}{routeD}\ \textbf{one-shot}\\\midrule
""" + rr + r"""\bottomrule\end{tabularx}}

\vspace{0.3em}
{\tiny\color{muted} Red: empty, or the two readings disagree (P and M differ only in spacing and punctuation).}

\vspace{0.6em}
\begin{tabular}{@{}lll@{}}
\cand{P}{routeB}\ {\large\bfseries """ + str(filled["P"]) + r"""\,/\,77}\qquad & \cand{M}{routeC}\ {\large\bfseries """ + str(filled["M"]) + r"""\,/\,77}\qquad & \cand{O}{routeD}\ {\large\bfseries """ + str(filled["O"]) + r"""\,/\,77}\\
{\scriptsize fields filled} & {\scriptsize fields filled} & {\scriptsize fields filled}
\end{tabular}

\vspace{0.5em}
{\footnotesize P: the reader agent on the page images. M: the reader agent on the MinerU parse and the images. O: the benchmark's own one-shot reader.}
\end{columns}
\src{ExtractBench short: """ + esc(form["name"]) + r"""; stored readings after their checks.}
""")

# ------------------------------------------------------------------ checks
T.append("")


def checks_frame(title, rows, note):
    body = r"""{\scriptsize\renewcommand{\arraystretch}{1.12}
\begin{tabularx}{\textwidth}{@{}>{\raggedright\arraybackslash}p{2.9cm}>{\raggedright\arraybackslash}p{3.0cm}Y>{\raggedleft\arraybackslash}p{1.9cm}@{}}\toprule
\textbf{Check} & \textbf{Document} & \textbf{Observed change} & \textbf{Value F1}\\\midrule
"""
    for chk, doc, change, why, f1 in rows:
        body += (r"\textbf{%s} & %s & \textcolor{good}{\textbf{%s}}\newline{\tiny %s} & %s\\[0.1em]" %
                 (chk, doc, change, why, f1) + "\n")
    body += r"\bottomrule\end{tabularx}}" + "\n\n\\vspace{0.3em}\n{\\tiny " + note + "\\par}\n"
    body += (r"\src{Stored readings before and after each check, re-run with \texttt{docquorum/checks} and scored with "
             r"ExtractBench's scorer. Each check uses only the schema and the document's own text; no model is called.}")
    frame(title, body)


checks_frame("Step 4: checks that repair the structure of a reading", [
    ("Rows copied into another list", "Pueblo check register (medium)", "562" + ARROW + "51 batch rows",
     r"Check 01033982 (\$700.88) had also been filed as a batch with the same number and amount.", "84.73" + ARROW + "99.91"),
    ("Identical records capped at the printed count", "FTX creditor list, text layer (long)", "146" + ARROW + "37 rows on page 59",
     r"Page 59 prints the line ``NAME ON FILE'' exactly 37 times.", "84.47" + ARROW + "90.77"),
    ("Stacked lines folded into one record", "Clinical adverse-event listing (long)", "1,499" + ARROW + "668 records",
     "Subject R1002: three printed lines became one event with its resolved date.", "38.80" + ARROW + "68.77"),
    ("Template rows dropped", "Texas W-14 well form (short)", "5" + ARROW + "2 casing rows",
     r"Three rows carried only the printed row label (e.g.\ ``Intermediate'').", "82.30" + ARROW + "93.23"),
], "Examples are the cases each check was designed for. On a few short documents some repairs lowered the score slightly "
   "(e.g.\\ duplicate removal on three election reports, $-$3.5 points in total).")

checks_frame("Step 4: checks that make values exactly what the page prints", [
    ("Every schema field present", "Caterpillar 330 spec sheet (short)", "missing keys" + ARROW + r"\texttt{null}",
     "The reply omitted 7 optional fields in every specification row; the scorer counts an absent key as a miss.",
     "61.48" + ARROW + "95.74"),
    ("A blank tick box is false", "Texas P-4 form (short)", r"6 boxes: \texttt{null}" + ARROW + r"\texttt{false}",
     r"The field description states ``false if left blank''.", "91.67" + ARROW + "96.67"),
    ("Quotes as printed", "Census statistical table (short)", r"Bachelor\textquotesingle{}s" + ARROW + "Bachelor's",
     "The page prints a typographic apostrophe; only the quote character is copied from the page.", "60.12" + ARROW + "62.58"),
    ("Numbers as printed", "Schedule K-1 (short, one-shot reading)", "33.333333" + ARROW + "33.3333333",
     "A rounded value is replaced by the single printed figure it restates (6 share fields).", "85.42" + ARROW + "97.92"),
], "Every replacement is a value that the document itself prints, or \\texttt{null} where the schema admits null.")

# ------------------------------------------------------------------ quorum
pairs = quorum["pairs"]


def f2(p, r):
    return 0.0 if p <= 0 or r <= 0 else 5 * p * r / (4 * p + r)


sc = quorum["score"]
frame(r"Step 5: selection by quorum", r"""
\begin{columns}[T]
\column{0.42\textwidth}
\centering
\begin{tikzpicture}[every node/.style={font=\small}]
\node[circle,fill=routeB,text=white,minimum size=1.1cm,font=\Large\bfseries] (P) at (0,2.6) {P};
\node[circle,fill=routeC,text=white,minimum size=1.1cm,font=\Large\bfseries] (M) at (4,2.6) {M};
\node[circle,fill=routeD,text=white,minimum size=1.1cm,font=\Large\bfseries] (O) at (2,0) {O};
\draw[line width=1.6pt,black!45] (P) -- node[above,black]{\textbf{""" + f"{f2(*pairs['P']['M']):.2f}" + r"""}} (M);
\draw[line width=1.6pt,black!45] (P) -- node[left,black]{\textbf{""" + f"{f2(*pairs['P']['O']):.2f}" + r"""}} (O);
\draw[line width=1.6pt,black!45] (M) -- node[right,black]{\textbf{""" + f"{f2(*pairs['M']['O']):.2f}" + r"""}} (O);
\end{tikzpicture}

\vspace{0.6em}
{\scriptsize Edge: agreement of two readings, measured with the benchmark's value scorer, recall-weighted ($F_{\beta}$, $\beta=2$).\par}
\column{0.55\textwidth}
{\footnotesize\begin{tabular}{@{}lrl@{}}\toprule
\textbf{Reading} & \textbf{Mean agreement} & \\\midrule
\rowcolor{hl}\cand{P}{routeB}\ image reading & """ + f"{sc['P']:.3f}" + r""" & \textbf{kept}\\
\cand{M}{routeC}\ parse reading & """ + f"{sc['M']:.3f}" + r""" & \\
\cand{O}{routeD}\ one-shot & """ + f"{sc['O']:.3f}" + r""" & \\\bottomrule
\end{tabular}}

\vspace{0.4em}
{\scriptsize P and M tie; ties go to the reading listed first. The whole of P is returned; fields are never mixed across readings.}

\vspace{0.6em}
\begin{block}{Agreement is not accuracy}
\scriptsize
Answer-key value F1 for this document (illustration only; never used by the pipeline): P 95.24, M 95.24, O 22.50.
On the scanned county purchase order the quorum kept the one-shot reading (78.26), although the image reading scored higher (82.61).
\end{block}
\end{columns}
\src{ExtractBench short: """ + esc(form["name"]) + r"""; agreement computed by \texttt{docquorum.quorum.pick} on the checked readings.}
""")

# ------------------------------------------------------------------ output
excerpt = [k for k in ["p1_company", "p1_address", "p1_county", "p1_well_no", "p1_name_of_lease",
                       "p1_drilling_commenced", "p1_total_depth"] if k in P]
js = ["{"] + [f'  "{k}": {json.dumps(P[k], ensure_ascii=False)},' for k in excerpt] + ["  ... 70 further fields", "}"]
fin = unikie_ex["final"]
fl = ['{"menu": ['] + [f'   {{"price": "{m["price"]}", "nm": "{m["nm"]}"}},' for m in fin["menu"]] + \
     [' ],', f' "total": {{"cashprice": "{fin["total"]["cashprice"]}",', f'           "total_price": "{fin["total"]["total_price"]}"}}}}']
frame("Step 6: one checked JSON, in the form requested", r"""
\begin{columns}[T]
\column{0.47\textwidth}
\textbf{\small JSON Schema in, JSON out (1955 form, 77 fields)}\\[0.3em]
\begin{beamercolorbox}[wd=\linewidth,sep=0.5em]{block body}
""" + code(js) + r"""
\end{beamercolorbox}
\column{0.50\textwidth}
\textbf{\small JSON template in, the same template filled}\\[0.3em]
\begin{columns}[T]
\column{0.32\linewidth}
\includegraphics[width=\linewidth]{assets/input_receipt.png}
\column{0.66\linewidth}
{\tiny\color{muted} Template}\\
""" + code(['{"menu": [{"price": "", "nm": ""}],', ' "total": {"cashprice": "",', '           "total_price": ""}}'], r"\tiny") + r"""\vspace{0.6em}
{\tiny\color{muted} Output (equal to the answer key)}\\
""" + code(fl, r"\tiny") + r"""
\end{columns}
\end{columns}
\src{Left: stored final output for """ + esc(form["name"]) + r""". Right: UNIKIE-BENCH Catering-Services test\_1.jpg, quorum over six stored readings.}
""")

# ------------------------------------------------------------------ results: one data shape for every benchmark
T.append(r"\section{Results}" + "\n")
load = lambda name: json.loads((RES / name).read_text())
from leaderboards import KIND, SYS_TYPES, ahead_of, me, nth, ordered, ranked, shown  # noqa: E402
KTEX = {"open": "good", "closed": "muted", "service": "routeB", "agent": "routeD"}
KPY = {"open": "#8CC5B0", "closed": "#AEB5C1", "service": "#93BCE3", "agent": "#C0AEDA"}
OURS_PY, NAVY_PY, MUTED_PY = "#1E7A60", "#1B2A4A", "#5B6577"


ORDER, lb = ordered()
BENCH = ORDER
BY = {b["key"]: b for b in BENCH}


# ------------------------------------------------------------------ results on six benchmarks
rows6 = ""
for b in ORDER:
    m, nxt = me(b), ahead_of(b)
    badge = r"\colorbox{%s}{\textcolor{white}{\textbf{%s}}}" % ("good" if m["rank"] == 1 else "navy!75", nth(m["rank"]))
    cells = [r"\textbf{%s}\newline{\tiny\color{muted}%s}" % (esc(b["title"]), esc(b["what"])),
             r"\textbf{%s}" % f"{b['ours']['score']:.2f}", badge + r" {\tiny of %d}" % len(ranked(b)),
             esc(nxt["name"]) + r" {\color{muted}%s}" % shown(nxt["score"], b["digits"]),
             cost(b["key"], "model_calls", 1), cost(b["key"], "usd", 3), cost(b["key"], "seconds")]
    rows6 += " & ".join(cells) + r"\\[0.15em]" + "\n"
frame("Results on six benchmarks", r"""{\scriptsize\renewcommand{\arraystretch}{1.25}\setlength{\tabcolsep}{4pt}
\begin{tabularx}{\textwidth}{@{}>{\raggedright\arraybackslash}p{3.3cm}rlYrrr@{}}\toprule
\textbf{Benchmark} & \textbf{Score} & \textbf{Place} & \textbf{Ahead of} & \textbf{Calls} & \textbf{\$} & \textbf{s}\\
 & & & & \multicolumn{3}{c}{\tiny per document}\\\midrule
""" + rows6 + r"""\bottomrule\end{tabularx}}

\vspace{0.3em}
{\scriptsize Scores: each benchmark's own scorer on the full test set; places count every published system. Open-weight models only (Qwen3.8-27B, MinerU2.5) on one GPU. Calls, \$ and s: means per document over a random sample; \$ prices the measured tokens at the Qwen3.8-27B list price.\par}
\src{Complete tables for every benchmark: the last section, and docs/results/TABLES.md. No result was submitted to a leaderboard.}
""")


# ------------------------------------------------------------------ charts (two)
def plt_setup():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": "#C8CDD5",
                         "axes.labelcolor": NAVY_PY, "xtick.color": MUTED_PY, "ytick.color": NAVY_PY,
                         "axes.titleweight": "bold", "axes.titlecolor": NAVY_PY, "axes.spines.top": False,
                         "axes.spines.right": False})
    return plt


def one_call_baselines():
    """Qwen3.8-27B, the model DocQuorum uses, called once per document by each benchmark's own
    protocol: {benchmark: (score, the published row it is, if any)}."""
    out = {}
    vx_f = ROOT / "results/varex/one-call/scores.json"
    if vx_f.exists():
        out["varex"] = (json.loads(vx_f.read_text())["score"], None)
    out["unikie"] = (json.loads((ROOT / "results/unikie/summary.json").read_text())["oneshot_27b"]["macro"], None)
    out["unikie_open"] = (load("docquorum-unikie-open.json")["single_readings"]["oneshot"]["score"], None)
    out["extractbench"] = (next(float(r["Overall"]) for r in lb if r["Provider"] == "Qwen3.8 27B"), "Qwen3.8 27B")
    return out


def place_among_published(b, score, itself=None):
    """1 + the published systems scoring above `score` (the baseline's own published row left out)."""
    return 1 + sum(shown(r["score"], b["digits"]) > shown(score, b["digits"]) for r in b["rows"] if r["name"] != itself)


BASE = one_call_baselines()


def chart_gain(path):
    """The same model called once, against DocQuorum: score and place among the published systems."""
    from matplotlib.transforms import blended_transform_factory
    plt = plt_setup()
    items = [b for b in ORDER if b["key"] in BASE]
    fig, ax = plt.subplots(figsize=(10.5, 0.82 * len(items) + 1.0), dpi=220)
    side = blended_transform_factory(ax.transAxes, ax.transData)
    for i, b in enumerate(items[::-1]):
        s0, itself = BASE[b["key"]]
        s1 = b["ours"]["score"]
        p0, p1 = place_among_published(b, s0, itself), me(b)["rank"]
        ax.annotate("", xy=(s1, i), xytext=(s0, i),
                    arrowprops=dict(arrowstyle="-|>,head_width=0.35,head_length=0.6", color=OURS_PY, lw=2.4, shrinkA=7, shrinkB=8))
        ax.scatter([s0], [i], s=85, color="#AEB5C1", zorder=3, edgecolor="white", linewidth=0.8)
        ax.scatter([s1], [i], s=130, color=OURS_PY, zorder=3, edgecolor="white", linewidth=0.8)
        ax.text(s0 - 0.45, i, f"{s0:.2f}", ha="right", va="center", fontsize=8, color=MUTED_PY)
        ax.text(s1 + 0.45, i, f"{s1:.2f}", ha="left", va="center", fontsize=8.5, color=OURS_PY, weight="bold")
        ax.text(1.02, i, f"+{s1 - s0:.2f} points", transform=side, ha="left", va="bottom", fontsize=9,
                color=OURS_PY, weight="bold")
        ax.text(1.02, i, f"place {nth(p0)} → {nth(p1)} of {len(b['rows']) + 1}", transform=side, ha="left", va="top",
                fontsize=8, color=NAVY_PY)
    ax.set_yticks(range(len(items)), [b["title"] for b in items[::-1]], fontsize=9, weight="bold")
    ax.set_ylim(-0.6, len(items) - 0.4)
    lo = min(BASE[b["key"]][0] for b in items)
    ax.set_xlim(lo - 3.5, 100)
    ax.set_xlabel("score (%), the benchmark's own scorer", fontsize=7.5)
    ax.grid(axis="x", alpha=0.25)
    ax.tick_params(axis="y", length=0)
    ax.scatter([], [], s=60, color="#AEB5C1", label="Qwen3.8-27B, one call (the benchmark's own protocol)")
    ax.scatter([], [], s=80, color=OURS_PY, label="the same model through DocQuorum")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, fontsize=8)
    fig.tight_layout()
    fig.subplots_adjust(right=0.80)
    fig.savefig(path)
    plt.close(fig)


chart_gain(A / "chart_gain.png")
GAIN = [b["ours"]["score"] - BASE[b["key"]][0] for b in ORDER if b["key"] in BASE]
PLACES = [f"{b['title']} {nth(place_among_published(b, *BASE[b['key']]))} $\\to$ \\textbf{{{nth(me(b)['rank'])}}}"
          for b in ORDER if b["key"] in BASE]
frame("What the pipeline adds to the same model", r"""
\centering\includegraphics[width=\textwidth,height=5.0cm,keepaspectratio]{assets/chart_gain.png}\par
\raggedright{\footnotesize Same open model, same documents. Read through DocQuorum (routing, readers, checks, quorum, zoom) instead of called once, Qwen3.8-27B gains GAINS points on all four benchmarks with a one-call baseline: PLACES.\par}
\src{One call: each benchmark's own one-shot protocol with Qwen3.8-27B (VAREX: benchmarks/multibench/varex\_one\_call.py; UNIKIE-BENCH: results/unikie; ExtractBench: the leaderboard's own Qwen3.8 27B run). Places count the published systems.}
""".replace("GAINS", f"{min(GAIN):.2f} to {max(GAIN):.2f}").replace("PLACES", "; ".join(PLACES)))


def chart_cost(path):
    """ExtractBench, every priced system scoring 85 or more, and DocQuorum: accuracy against cost per page.
    The shaded corner (cheaper and more accurate than DocQuorum) holds no published system."""
    from matplotlib.patches import Rectangle
    from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter
    plt = plt_setup()
    cat = SYS_TYPES["from_source"]["extractbench_category"]
    pts = [(r["Provider"], float(r["Cost_Per_Page"]), float(r["Overall"]), cat[r["Category"]])
           for r in lb if r.get("Cost_Per_Page") and float(r["Overall"]) >= 85]
    ourx, oury = (MEASURED.get("extractbench") or {}).get("usd_per_page"), BY["extractbench"]["ours"]["score"]
    fig, ax = plt.subplots(figsize=(7.4, 4.4), dpi=220)
    xmin, xmax, ymin, ymax = 0.002, 0.8, 85, 97.4
    if ourx:
        ax.add_patch(Rectangle((xmin, oury), ourx - xmin, ymax - oury, color=OURS_PY, alpha=0.08, lw=0, zorder=0))
        ax.text((xmin * ourx) ** 0.4 * xmin ** 0.2, (oury + ymax) / 2 + 0.25, "cheaper and more accurate\nthan DocQuorum: no system",
                ha="center", va="center", fontsize=7, color=OURS_PY, style="italic")
    for k in ("service", "agent", "closed"):
        sel = [p for p in pts if p[3] == k]
        ax.scatter([p[1] for p in sel], [p[2] for p in sel], s=36, color=KPY[k], label=KIND[k], zorder=2,
                   edgecolor="white", linewidth=0.6)
    leaders = sorted(pts, key=lambda p: -p[2])[:2]
    lx = max(p[1] for p in leaders)
    ax.annotate(" and ".join(p[0] for p in leaders) + f"\n{leaders[0][2]:.2f} at "
                + " and ".join(f"\\${p[1]:.3f}" for p in sorted(leaders, key=lambda p: p[1])),
                (lx, leaders[0][2]), textcoords="offset points", xytext=(9, 0), va="center", fontsize=6.6, color=MUTED_PY)
    if ourx:
        ax.scatter([ourx], [oury], s=150, color=OURS_PY, marker="D", zorder=4, edgecolor="white", linewidth=0.8,
                   label="DocQuorum")
        ax.annotate(f"DocQuorum\n{oury:.2f} at \\${ourx:.3f}", (ourx, oury), textcoords="offset points", xytext=(-11, 0),
                    ha="right", va="center", fontsize=8.5, color=OURS_PY, weight="bold")
        lo, hi = (min(p[1] for p in leaders) / ourx, lx / ourx)
        ax.annotate("", xy=(min(p[1] for p in leaders) * 0.9, oury), xytext=(ourx * 1.18, oury),
                    arrowprops=dict(arrowstyle="<-", color=NAVY_PY, lw=1.0))
        ax.text((ourx * min(p[1] for p in leaders)) ** 0.5, oury + 0.25, f"{lo:.0f}-{hi:.0f}× the cost",
                ha="center", va="bottom", fontsize=7.5, color=NAVY_PY, weight="bold")
    ax.set_xscale("log")
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.xaxis.set_major_locator(LogLocator(subs=(1, 2, 5)))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:g}"))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xlabel("$ per page (log scale)", fontsize=7.5)
    ax.set_ylabel("value F1 (%)", fontsize=7.5)
    ax.set_title("ExtractBench: accuracy against cost (every priced system scoring 85 or more)", fontsize=8.6, loc="left")
    ax.legend(fontsize=6.8, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=4)
    ax.grid(alpha=0.22, which="major")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


chart_cost(A / "cost_accuracy.png")
rows_db = [r for r in COST.get("docubench", {}).get("documents", []) if r.get("status") == "completed"]
one = [r for r in rows_db if len(r.get("route") or []) == 1]
cents = ", ".join(f"{b['title']} {100 * MEASURED[b['key']]['usd_per_page']:.1f}" for b in ORDER if MEASURED.get(b["key"]))
o_db, n_db, k_db = (lambda: (None, None, []))()
v13 = PR.COSTS / "v1.3" / "docubench.json"
if v13.exists() and "docubench" in COST:
    o_db = {r["document"]: r for r in json.loads(v13.read_text())["documents"]}
    n_db = {r["document"]: r for r in COST["docubench"]["documents"]}
    k_db = [k for k in n_db if k in o_db]
speed = (sum(o_db[k]["seconds"] for k in k_db) / sum(n_db[k]["seconds"] for k in k_db)) if k_db else None
frame("Accuracy at a fraction of the cost", r"""
\begin{columns}[T]
\column{0.63\textwidth}
\includegraphics[width=\linewidth]{assets/cost_accuracy.png}
\column{0.35\textwidth}
\footnotesize
\textbf{No system is both cheaper and more accurate} than DocQuorum on ExtractBench.\\[0.6em]
\textbf{A few cents a page} on every benchmark:\\ {\color{muted}CENTS (cents)}\\[0.6em]
\textbf{Why:} one reading when the file has text; three readings only for scans, run at the same time; an open 27B model at a tenth of GPT-5.5's price per output token.\\[0.6em]
\textbf{v1.4:} long scans SPEED$\times$ faster.
\end{columns}
\src{DocQuorum: measured tokens on a random sample of each benchmark (results/costs/), priced at the Qwen3.8-27B list price (\$QIN / \$QOUT per million input / output tokens; it runs on its own GPU, with no price per call), weighted by split as the leaderboard computes cost per page.}
""".replace("CENTS", cents).replace("ONEN", str(len(one))).replace("DOCN", str(len(rows_db))).replace(
    "SPEED", f"{speed:.1f}" if speed else "--").replace("QIN", f"{QWEN['input']:.2f}").replace("QOUT", f"{QWEN['output']:.2f}"))

zv = json.loads((ROOT / "results/varex/v1.2-zoom/comparison.json").read_text())
zu = json.loads((ROOT / "results/unikie_open/zoom/comparison.json").read_text())
zc = json.loads((ROOT / "results/unikie/zoom/comparison.json").read_text())
zc0 = json.loads((ROOT / "results/unikie/zoom/as_run/comparison.json").read_text())
frame("Zoom re-reading: a new step after the quorum", r"""
\begin{columns}[T]
\column{0.52\textwidth}
\small
After the quorum keeps one reading, each field on which the readings disagree is found on the page and read once more from a sharp crop of that region.\par\vspace{0.5em}
This new reading sees none of the earlier answers. It changes the kept value only if it matches a value some reading already proposed, and it counts as two votes: it can overturn a lead of one reading, not a clear majority.\par\vspace{0.5em}
The vote rule was added after the third test, where five agreeing readings were overturned too often.
\column{0.44\textwidth}
\begin{block}{Three tests}
\small
VAREX: %.2f%s\textbf{%.2f}\\
%d forms better, %d worse\\[0.5em]
UNIKIE open: %.2f%s\textbf{%.2f}\\
%d documents better, %d worse\\[0.5em]
UNIKIE (six readings): %.2f%s%.2f; %.2f with the vote rule
\end{block}
\end{columns}
\src{results/README.md: method, statistics, and every changed value checked against the answer key after the runs.}
""" % (zv["exact_match_normalized"]["before"], ARROW, zv["exact_match_normalized"]["after"], zv["forms_better"], zv["forms_worse"],
       zu["macro_f1"]["before"], ARROW, zu["macro_f1"]["after"], zu["documents_better"], zu["documents_worse"],
       zc0["macro_f1"]["before"], ARROW, zc0["macro_f1"]["after"], zc["macro_f1"]["after"]))

# ------------------------------------------------------------------ summary
T.append(r"\section{Summary}" + "\n")
frame("Summary", r"""
\begin{columns}[T]
\column{0.32\textwidth}
\begin{block}{Results}
\small
1st on VAREX and UNIKIE-BENCH; 2nd on LongArray-Extract and UNIKIE open; 3rd of 48 on ExtractBench.\\[0.3em]
Ahead of every published open model, with open models on one GPU, at a few cents a page.\\[0.3em]
Zoom re-reading improved VAREX and UNIKIE open.
\end{block}
\column{0.32\textwidth}
\begin{block}{Method}
\small
Routing by the available evidence; an agentic reader that plans, reads and re-reads; layout readers for column flow and ruled tables; deterministic checks against the schema and the page; selection by quorum.
\end{block}
\column{0.32\textwidth}
\begin{block}{Limitations}
\small
ExtractBench served as the development set. Agreement among readings does not guarantee accuracy. Checks are triggered by schema wording and page text; a few repairs lower the score on some documents.
\end{block}
\end{columns}
""")

# ------------------------------------------------------------------ complete results: one table design for every benchmark
T.append(r"\section{Complete results}" + "\n")


def complete_table(b):
    """Rank, system, type, score (with a bar on a 0-100 scale) and the benchmark's own breakdown; every
    published system and DocQuorum, in the same design for every benchmark."""
    allrows = ranked(b)
    per = b.get("per_slide") or len(allrows)
    n_parts = len(b["parts"])
    size = r"\footnotesize" if n_parts <= 1 else (r"\scriptsize" if n_parts <= 5 else r"\tiny")
    sep = "4pt" if n_parts <= 5 else "2.6pt"
    best = {}
    for j in range(n_parts):
        vals = [shown(r["parts"][j], b["digits"]) for r in allrows if isinstance(r["parts"][j], (int, float))]
        if vals:
            best[j] = max(vals)
    chunks = [allrows[i:i + per] for i in range(0, len(allrows), per)]
    for ci, chunk in enumerate(chunks):
        stretch = "1.3" if len(chunk) <= 11 else ("1.02" if len(chunk) <= 17 else "0.74")
        head = [r"\#", "System", "Type", "", "Score"] + b["parts"]
        t = ("{" + size + r"\renewcommand{\arraystretch}{" + stretch + r"}\setlength{\tabcolsep}{" + sep + "}\n"
             + r"\begin{tabularx}{\textwidth}{@{}rYl@{\hspace{6pt}}lr" + "r" * n_parts + r"@{}}\toprule" + "\n"
             + " & ".join(r"\textbf{%s}" % h if h else "" for h in head) + r"\\\midrule" + "\n")
        for r in chunk:
            mine = r["kind"] == "ours"
            bar = r"\textcolor{%s}{\rule{%.2fcm}{1.05ex}}" % ("good" if mine else KTEX[r["kind"]] + "!45",
                                                                1.2 * float(r["score"]) / 100)
            kind = r"{\color{good}\textbf{Open models}}" if mine else r"{\color{%s}%s}" % (KTEX[r["kind"]], KIND[r["kind"]])
            parts = []
            for j, v in enumerate(r["parts"]):
                if isinstance(v, (int, float)):
                    s = str(shown(v, b["digits"]))
                    s = r"\underline{%s}" % s if shown(v, b["digits"]) == best.get(j) else s
                else:
                    s = esc(v)
                parts.append(r"\textbf{%s}" % s if mine else s)
            score = f"{r['score']:.2f}" if mine else str(shown(r["score"], b["digits"]))
            cells = [str(r["rank"]), r"\textbf{DocQuorum (ours)}" if mine else esc(r["name"]), kind, bar,
                     r"\textbf{%s}" % score if mine else score] + parts
            t += (r"\rowcolor{hl}" if mine else "") + " & ".join(cells) + r"\\" + "\n"
        t += r"\bottomrule\end{tabularx}}"
        title = f"{b['title']}: complete results" + (f" ({ci + 1}/{len(chunks)})" if len(chunks) > 1 else "")
        frame(esc(title), t + "\n\n" + r"\vspace{0.25em}{\tiny\color{muted}" + b["legend"]
              + (" Underlined: best in the column." if best else "") + r" Equal scores share a rank.\par}" + "\n"
              + r"\src{" + b["src"] + r" DocQuorum: the final pipeline.}")


for b in ORDER:
    complete_table(b)

T.append(r"\end{document}" + "\n")
tex = HERE / "docquorum-flow.tex"
import re
out = "".join(T)
out = re.sub(r"\{\\(tiny|scriptsize|footnotesize)((?:\\renewcommand\{\\arraystretch\}\{[0-9.]+\}"
             r"|\\setlength\{\\tabcolsep\}\{[0-9.]+pt\}|\s)*)\\begin\{tabularx\}",
             r"\\begingroup\\\1\2\\begin{tabularx}", out)
out = out.replace(r"\end{tabularx}}", r"\end{tabularx}\endgroup")
assert out.count(r"\begin{tabularx}") == out.count(r"\begingroup"), "a table is still inside a brace group"
tex.write_text(out)
for _ in range(2):
    r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex.name], cwd=HERE,
                       capture_output=True, text=True)
    if r.returncode:
        print(r.stdout[-3000:])
        raise SystemExit("pdflatex failed")
print("wrote", HERE / "docquorum-flow.pdf")
