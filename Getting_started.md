# Running AMIE3 for rule mining

`run_amie.py` is a thin CLI wrapper around AMIE3, invoked as a Java subprocess:

```bash
python run_amie.py public_data/mario.tsv \
    -o public_data/mario_rules.csv \
    --mins 1 --minis 1 --minhc 0 --minc 0 --minpca 0
```

AMIE3's plain-text stdout table is parsed and written out as CSV
(`rule, body, head, head_coverage, std_confidence, pca_confidence,
positive_examples, body_size, pca_body_size, functional_variable`).

Note: AMIE's own defaults (`-mins`/`-minis 100`, `-minhc 0.01`) are tuned for
large knowledge bases and will silently mine zero rules on a graph this
small. Pass `--mins 1 --minis 1 --minhc 0` (and optionally `--minc 0
--minpca 0`) as shown above. Run `python run_amie.py --help` for all options.

# Setup

**Python dependencies**: `networkx`, `numpy`, `pandas`, `rdflib`, `pygraft`,
plus Jupyter to run the notebooks. There is currently no pinned
requirements/environment file in this repo. These are installed in the
`NeSy` pyenv virtualenv (`~/.pyenv/versions/NeSy/bin/python`), not the system
interpreter -- run PyGraft scripts/notebooks with that interpreter.

**Footgun**: this repo has a vendored, git-ignored `./pygraft/` source clone
at the repo root (see `.gitignore`; obtained separately, see "AMIE/ and
pygraft/ directories" below). If you run `import pygraft` with an interpreter
that doesn't have the real `pygraft` package pip-installed, Python silently
resolves the import to that directory as an empty namespace package instead
of raising `ModuleNotFoundError` -- so a run against the wrong interpreter
doesn't fail with a clear "not installed" error, it fails later with a
confusing `AttributeError: module 'pygraft' has no attribute 'generate_kg'`
(or similar). If you see that error, you're on the wrong interpreter -- use
`~/.pyenv/versions/NeSy/bin/python`.

**AMIE3**: `run_amie.py` shells out to a local AMIE3 `.jar` (default:
`amie3.5.1.jar` next to the script, override with `--jar`). It requires a
Java runtime on `PATH`. Download AMIE3 from the
[AMIE repository](https://github.com/dig-team/amie):`*.jar` files are
git-ignored here and not checked in.

**AMIE/ and pygraft/ directories**: these are vendored, git-ignored copies
of the two upstream projects' full source (used for reference/local
development, e.g. `AMIE/inference` scripts and building AMIE from source).
They aren't required to run the notebooks and aren't included when this repo is cloned.
Obtain them separately from [dig-team/amie](https://github.com/dig-team/amie) and
[nicolas-hbt/pygraft](https://github.com/nicolas-hbt/pygraft) if you need
them.
