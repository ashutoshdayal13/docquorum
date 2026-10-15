"""Write ppt/flow/docquorum-flow.tex (LaTeX Beamer) from the assets and the results snapshots, and compile it.

    python ppt/flow/build_beamer.py       (after ppt/flow/make_assets.py; needs pdflatex with beamer/metropolis)

Every number on the slides comes from ppt/flow/assets/*.json or docs/results/.
"""
import csv
import json
import subprocess
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
A = HERE / "assets"
RES = ROOT / "docs" / "results"
facts = json.loads((A / "facts.json").read_text())
quorum = json.loads((A / "quorum_example.json").read_text())
unikie_ex = json.loads((A / "unikie_example.json").read_text())


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
\item Results on six benchmarks; zoom re-reading
\item Summary
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
\includegraphics[width=\textwidth,height=6.25cm,keepaspectratio]{assets/pipeline.png}
\src{Pipeline figure (generated with Codex), describing the single-document entry point \texttt{docquorum.extract}; the lower panel shows the reader agent's plan--act--observe loop.}
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

# ------------------------------------------------------------------ results: ExtractBench (complete)
T.append(r"\section{Results}" + "\n")
eb = json.loads((RES / "docquorum-extractbench.json").read_text())["stored_primary"]
with (RES / "extractbench-leaderboard.csv").open(newline="") as fh:
    lb = sorted(csv.DictReader(fh), key=lambda r: (-Decimal(r["Overall"]), Decimal(r["Cost_Per_Page"] or "Infinity")))
CAT = {"LlamaExtract": "Commercial service", "Specialized APIs": "Commercial service", "Commercial VLM": "Commercial model",
       "Coding Agents": "Coding agent", "OSS": "Open model"}
ours = {"Provider": r"\textbf{DocQuorum (ours)}", "Category": "Open model (27B)", "Overall": eb["score"],
        "Short": eb["per_split"]["short"], "Medium": eb["per_split"]["medium"], "Long": eb["per_split"]["long"], "ours": True}
at = sum(disp(r["Overall"]) >= disp(ours["Overall"]) for r in lb)
full = lb[:at] + [ours] + lb[at:]
rk = ranks([r["Overall"] for r in full])
assert rk[full.index(ours)] == 3 and len(full) == 48


def eb_table(part, lo, hi):
    t = r"""{\scriptsize\renewcommand{\arraystretch}{1.0}\setlength{\tabcolsep}{5pt}
\begin{tabularx}{\textwidth}{@{}rYlrrrr@{}}\toprule
\textbf{\#} & \textbf{System} & \textbf{Type} & \textbf{Short} & \textbf{Medium} & \textbf{Long} & \textbf{Overall}\\\midrule
"""
    for k, r in zip(rk[lo:hi], full[lo:hi]):
        mine = r.get("ours")
        cells = [str(k), r["Provider"] if mine else esc(r["Provider"]), CAT.get(r["Category"], esc(r["Category"])),
                 str(disp(r["Short"])), str(disp(r["Medium"])), str(disp(r["Long"])), str(disp(r["Overall"]))]
        if mine:
            cells = [r"\textbf{%s}" % c if i != 1 else c for i, c in enumerate(cells)]
        t += (r"\rowcolor{hl}" if mine else "") + " & ".join(cells) + r"\\" + "\n"
    t += r"\bottomrule\end{tabularx}}"
    frame(r"ExtractBench: complete results (%d/3)" % part, t + r"""
\src{ExtractBench leaderboard, snapshot of 2 October 2026 (47 published systems) and DocQuorum. Value F1 (\%) by the benchmark's scorer over 370 PDFs (252 short, 98 medium, 20 long); Overall is the mean over all documents. Equal scores share a rank.}
""")


eb_table(1, 0, 16)
eb_table(2, 16, 32)
eb_table(3, 32, 48)

# ------------------------------------------------------------------ results: UNIKIE (complete)
pub = json.loads((RES / "unikie-published.json").read_text())
uj = json.loads((RES / "docquorum-unikie.json").read_text())
u = uj["variants"][uj["headline"]]          # the reported configuration
cols = pub["columns"][:-1]
urows = [(n, v, "C") for n, v in pub["closed_source"].items()] + [(n, v, "O") for n, v in pub["open_source"].items()]
urows.sort(key=lambda x: -x[1][-1])
ou = (r"\textbf{DocQuorum (ours)}", [u["per_scenario"][c] for c in cols] + [u["score"]], "O")
at = sum(disp(v[-1]) >= disp(u["score"]) for _, v, _ in urows)
ufull = urows[:at] + [ou] + urows[at:]
urk = ranks([v[-1] for _, v, _ in ufull])
best = [max(disp(v[j]) for _, v, _ in ufull) for j in range(len(cols) + 1)]
abbr = ["Ret.", "Cat.", "Com.", "Acc.", "Post.", "Adm.", "Edu.", "Adv.", "Tax", "Med.", "Nut.", "Avg."]
ut = r"""{\scriptsize\renewcommand{\arraystretch}{0.9}\setlength{\tabcolsep}{3.2pt}
\begin{tabularx}{\textwidth}{@{}rYc*{11}{r}r@{}}\toprule
\textbf{\#} & \textbf{System} & & """ + " & ".join(r"\textbf{%s}" % a for a in abbr) + r"""\\\midrule
"""
for k, (n, v, kind) in zip(urk, ufull):
    mine = n.startswith(r"\textbf{DocQuorum")
    cells = [str(k), n if mine else esc(n), kind]
    for j, x in enumerate(v):
        s = str(disp(x))
        if disp(x) == best[j]:
            s = r"\underline{%s}" % s
        cells.append(r"\textbf{%s}" % s if mine else s)
    ut += (r"\rowcolor{hl}" if mine else "") + " & ".join(cells) + r"\\" + "\n"
ut += r"\bottomrule\end{tabularx}}"
frame("UNIKIE-BENCH: complete results", ut + r"""

\vspace{0.3em}
{\tiny Ret.\ Retail; Cat.\ Catering services; Com.\ Commercial; Acc.\ Accommodation; Post.\ Postal label; Adm.\ Administrative; Edu.\ Education; Adv.\ Advertisement; Tax: Tax-compliant; Med.\ Medical services; Nut.\ Nutrition label; Avg.\ macro average. C: closed model; O: open model. Underlined: best in the column.\par}
\src{UNIKIE-BENCH (ACL 2026), Table 4: 15 published systems; F1 (\%) by the benchmark's evaluator on 4,472 images, every input capped at 1,605,632 pixels. DocQuorum: quorum over six readings from three open models; small images enlarged before reading.}
""")

# ------------------------------------------------------------------ results on six benchmarks
def place(score, published, digits):
    """1 + published scores above ours, compared at the published precision."""
    q = Decimal(1).scaleb(-digits)
    sh = lambda v: Decimal(str(v)).quantize(q, rounding=ROUND_HALF_UP)
    return 1 + sum(sh(v) > sh(score) for _, v in published)


load = lambda name: json.loads((RES / name).read_text())
vx, la, uo, db = (load(f"docquorum-{k}.json") for k in ("varex", "longarray", "unikie-open", "docubench"))
pv = [(r["system"], r["em"]) for r in load("varex-published.json")["systems"]]
pl = [(r["system"], r["score"]) for r in load("longarray-published.json")["systems"]]
puo = [(n, v[-1]) for k in ("closed_source", "open_source") for n, v in load("unikie-open-published.json")[k].items()]
pdb = [(r["system"], r["score"]) for r in load("docubench-published.json")["systems"]]
puk = [(n, v[-1]) for n, v, _ in urows]
peb = [(r["Provider"], float(r["Overall"])) for r in lb]
ORD = {1: "1st", 2: "2nd", 3: "3rd"}
bench = [  # (name, ours, published, digits, note)
    ("VAREX (1,777 government forms)", vx["score"], pv, 1, "with zoom re-reading"),
    ("UNIKIE-BENCH (4,472 images)", u["score"], puk, 2, ""),
    ("LongArray-Extract (45 long documents)", la["score"], pl, 1, ""),
    ("UNIKIE-BENCH open category (1,661 documents)", uo["score"], puo, 2, "with zoom re-reading"),
    ("ExtractBench (370 PDFs)", eb["score"], peb, 2, "development set"),
    ("DocuBench (72 documents, 10 file types)", db["score"], pdb, 2, ""),
]
rows6 = ""
for name, score, published, digits, note in sorted(bench, key=lambda b: place(b[1], b[2], b[3])):
    k = place(score, published, digits)
    top = max(published, key=lambda r: r[1])            # the best published system
    other = (r"next: %s %s" if k == 1 else r"1st: %s %s") % (esc(top[0]), f"{top[1]:.{digits}f}")
    cells = [esc(name) + (r" {\footnotesize(%s)}" % note if note else ""), r"\textbf{%.2f}" % score,
             (r"\textbf{%s}" if k == 1 else "%s") % f"{ORD.get(k, f'{k}th')} of {len(published) + 1}", esc(other)]
    rows6 += (r"\rowcolor{hl}" if k == 1 else "") + " & ".join(cells) + r"\\" + "\n"
frame("Results on six benchmarks", r"""{\footnotesize\renewcommand{\arraystretch}{1.25}
\begin{tabularx}{\textwidth}{@{}Yrll@{}}\toprule
\textbf{Benchmark} & \textbf{DocQuorum} & \textbf{Place} & \textbf{Comparison}\\\midrule
""" + rows6 + r"""\bottomrule\end{tabularx}}

\vspace{0.6em}
{\small Each score is the benchmark's own scorer on the full test set, with open-weight models (Qwen3.8-27B and MinerU2.5) on one GPU. Places count every published system.\par}
\src{docs/results/: one complete table per benchmark (TABLES.md). No result was submitted to a leaderboard.}
""")

zv = load("../../results/varex-zoom/comparison.json")
zu = json.loads((ROOT / "results/unikie_open/zoom/comparison.json").read_text())
frame("Zoom re-reading: a new step after the quorum", r"""
\begin{columns}[T]
\column{0.52\textwidth}
\small
After the quorum keeps one reading, each field on which the readings disagree is found on the page and read once more from a sharp crop of that region.\par\vspace{0.5em}
This new reading sees none of the earlier answers. The kept value changes only if it matches a value some reading already proposed.\par\vspace{0.5em}
The design was fixed on ExtractBench, then run once on two other benchmarks.
\column{0.44\textwidth}
\begin{block}{Held-out results}
\small
VAREX: %.2f%s\textbf{%.2f}\\
%d forms better, %d worse\\[0.5em]
UNIKIE open: %.2f%s\textbf{%.2f}\\
%d documents better, %d worse\\[0.5em]
Both are far beyond chance (sign test).
\end{block}
\end{columns}
\src{results/README.md: method, statistics, and every changed value checked against the answer key after the runs.}
""" % (zv["exact_match_normalized"]["before"], ARROW, zv["exact_match_normalized"]["after"], zv["forms_better"], zv["forms_worse"],
       zu["macro_f1"]["before"], ARROW, zu["macro_f1"]["after"], zu["documents_better"], zu["documents_worse"]))

# ------------------------------------------------------------------ summary
T.append(r"\section{Summary}" + "\n")
frame("Summary", r"""
\begin{columns}[T]
\column{0.32\textwidth}
\begin{block}{Results}
\small
1st on VAREX and UNIKIE-BENCH; 2nd on LongArray-Extract and UNIKIE open; 3rd on ExtractBench.\\[0.4em]
A new step, zoom re-reading, improved both benchmarks it was tested on.\\[0.4em]
Open-weight models on one GPU.
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
