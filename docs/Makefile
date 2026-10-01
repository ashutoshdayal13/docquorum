LATEX = pdflatex
FLAGS = -interaction=nonstopmode -halt-on-error

.PHONY: all clean
all: docquorum.pdf fig/pipeline.pdf

docquorum.pdf: docquorum.tex fig/pipeline.tex
	$(LATEX) $(FLAGS) docquorum.tex
	$(LATEX) $(FLAGS) docquorum.tex

fig/pipeline.pdf: fig/pipeline.tex fig/pipeline-standalone.tex
	cd fig && $(LATEX) $(FLAGS) -jobname=pipeline pipeline-standalone.tex

clean:
	rm -f *.aux *.log *.out fig/*.aux fig/*.log fig/*.out
