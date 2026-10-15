LATEX = pdflatex
FLAGS = -interaction=nonstopmode -halt-on-error

.PHONY: all verify clean
all: docquorum.pdf

docquorum.pdf: walkthrough.tex $(wildcard assets/*.png)
	$(LATEX) $(FLAGS) walkthrough.tex
	$(LATEX) $(FLAGS) walkthrough.tex
	cp walkthrough.pdf docquorum.pdf

verify:
	python3 verify_examples.py

clean:
	rm -f walkthrough.aux walkthrough.log walkthrough.out walkthrough.nav walkthrough.snm walkthrough.toc walkthrough.vrb
