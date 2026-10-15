LATEX = pdflatex
FLAGS = -interaction=nonstopmode -halt-on-error
PDFTOPPM ?= pdftoppm

.PHONY: all preview clean
all: docquorum.pdf fig/pipeline.pdf fig/docquorum-pipeline-imagegen-v5.pdf
preview: fig/pipeline.png

docquorum.pdf: docquorum.tex schema-demos.tex results-tables.tex $(wildcard examples/*.json) fig/docquorum-pipeline-imagegen-v5.png fig/pipeline.tex fig/pictograms.tex fig/evidence-sharing.tex fig/scan-trace.tex fig/route-examples.tex
	$(LATEX) $(FLAGS) docquorum.tex
	$(LATEX) $(FLAGS) docquorum.tex

results-tables.tex: results/generate_tables.py $(wildcard results/*.json) results/extractbench-leaderboard.csv
	python3 results/generate_tables.py

fig/pipeline.pdf: fig/pipeline.tex fig/pipeline-standalone.tex fig/pictograms.tex
	cd fig && $(LATEX) $(FLAGS) -jobname=pipeline pipeline-standalone.tex

fig/pipeline.png: fig/pipeline.pdf
	$(PDFTOPPM) -singlefile -scale-to 1800 -png fig/pipeline.pdf fig/pipeline

fig/docquorum-pipeline-imagegen-v5.pdf: fig/docquorum-pipeline-imagegen-v5.tex fig/docquorum-pipeline-imagegen-v5.png
	cd fig && $(LATEX) $(FLAGS) docquorum-pipeline-imagegen-v5.tex

clean:
	rm -f *.aux *.log *.out fig/*.aux fig/*.log fig/*.out
