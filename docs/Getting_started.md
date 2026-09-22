# Running AMIE3 for rule mining

`run_amie.py` is a thin CLI wrapper around AMIE3, invoked as a Java subprocess:

```bash
python run_amie.py .data/lung_cancer/lung_cancer.nt -o output/lung_cancer_rules.csv
```

AMIE3's plain-text stdout table is parsed and written out as CSV
(`rule, body, head, head_coverage, std_confidence, pca_confidence,
positive_examples, body_size, pca_body_size, functional_variable`). AMIE's
own defaults (`-mins`/`-minis 100`, `-minhc 0.01`) are what's used above,
and they're fine here -- lung_cancer has real structure well above those
thresholds (see `.data/lung_cancer/lung_cancer.csv` for the rules already
mined from it this way).

Note: those same defaults are tuned for large knowledge bases and will
silently mine zero (or only trivial) rules on a small or logically-thin
graph. If a run comes back empty, pass `--mins 1 --minis 1 --minhc 0`
(and optionally `--minc 0 --minpca 0`) to see everything AMIE considers,
then judge by `head_coverage`/`positive_examples` whether what comes back
is real structure or noise (see the French royalty findings in the main
[`README.md`](../README.md) for a worked example of both). Run
`python run_amie.py --help` for all options.

# Setup

**Python dependencies**: `pip install -r requirements.txt`, hand-curated to
exactly what this repo's own scripts import: `networkx`, `numpy`, `scipy`,
`pandas`, `grakel` (Weisfeiler-Lehman kernel, see `kernel_report.py`), and
`matplotlib` (see `plots.py`). These are installed in the `NeSy` pyenv
virtualenv (`~/.pyenv/versions/NeSy/bin/python`), not the system
interpreter -- run every script in this repo with that interpreter.

**Scope**: this repo evaluates knowledge graphs, it doesn't generate them.
The real and synthetic graphs it compares (e.g. via PyGraft or SKGG) are
produced elsewhere and land pre-generated under `.data/` -- a machine-local
symlink into `~/Datasets/knowledge_graphs/`, gitignored and not part of
this repo. There's no PyGraft/rdflib dependency or vendored generator
source here because nothing in this repo's scripts generates a graph.

**AMIE3**: `run_amie.py` shells out to a local AMIE3 `.jar` (default:
`amie3.5.1.jar` next to the script, override with `--jar`). It requires a
Java runtime on `PATH`. Download AMIE3 from the
[AMIE repository](https://github.com/dig-team/amie): `*.jar` files are
git-ignored here and not checked in.
