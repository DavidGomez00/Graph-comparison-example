# Graph analysis and comparison

Tools and notebooks for generating a synthetic knowledge graph (KG) with
[PyGraft](https://github.com/nicolas-hbt/pygraft) from a small hand-authored
target graph (a "Mario" universe of characters and their relations), and for
comparing the two graphs both structurally (degree, triangles, clustering)
and logically (Horn rules mined with [AMIE3](https://github.com/dig-team/amie)).

The guiding question: how well does a schema-driven synthetic KG generator
reproduce the structural and logical properties of a real, hand-curated graph
that shares its schema?

## Repository layout

```
.
├── mario.yml                      # PyGraft config: schema + KG generation parameters
├── pygraft_generation.ipynb       # Generates the synthetic KG with PyGraft
├── graph_comparison.ipynb         # Compares target vs. synthetic graph
├── run_amie.py                    # CLI wrapper: run AMIE3 and export mined rules to CSV
├── output/mario/                  # Hand-crafted PyGraft schema + PyGraft's generated KG
│   ├── schema.rdf                 #   hand-customized schema (classes/relations named for Mario)
│   ├── generated_schema.rdf       #   PyGraft's auto-generated schema, kept for reference
│   ├── class_info.json            #   class hierarchy fed to PyGraft's KG generator
│   ├── relation_info.json         #   relation characteristics fed to PyGraft's KG generator
│   ├── kg_info.json               #   PyGraft's report on the KG it generated
│   └── full_graph.rdf             #   the synthetic KG PyGraft generated (RDF/XML)
├── public_data/                   # Target and synthetic graphs as plain triples, checked in
│   ├── mario.tsv / mario.csv      #   target graph (hand-authored)
│   └── pygraft.tsv / pygraft.csv  #   synthetic graph (parsed from full_graph.rdf)
├── .data/mario/                   # Local working copy of the same data (git-ignored)
├── amie3.5.1.jar                  # AMIE3 jar used by run_amie.py (git-ignored, not checked in)
├── AMIE/                          # Vendored copy of the AMIE rule-mining engine (git-ignored)
└── pygraft/                       # Vendored copy of the PyGraft KG generator (git-ignored)
```

`AMIE/` and `pygraft/` are separate upstream projects tracked in this working
copy as plain directories (not real git submodules — there's no
`.gitmodules`), and both are git-ignored. They are not part of this repo's
history and are not published with it; see below for how to obtain them.

## The target graph: "Mario"

[`public_data/mario.tsv`](public_data/mario.tsv) is a small, hand-authored
knowledge graph: 14 entities (Mario, Luigi, Bowser, Peach, ...), all typed
`Character`, connected by 119 triples over 5 relations —
`allyOf`, `enemyOf`, `brotherOf`, `servantOf`, `loves`. It exists purely as a
non-trivial but easy-to-inspect "ground truth" graph to generate a synthetic
counterpart from and compare against.

## Generating the synthetic graph — `pygraft_generation.ipynb`

[PyGraft](https://github.com/nicolas-hbt/pygraft) generates a synthetic KG
from a schema plus a set of numeric parameters (number of entities/triples,
relation properties such as symmetry/transitivity, class hierarchy depth,
etc.), configured in [`mario.yml`](mario.yml).

Rather than let PyGraft invent generic class/relation names (`C1`, `R1`, ...),
the schema in [`output/mario/schema.rdf`](output/mario/schema.rdf) (and its
matching [`class_info.json`](output/mario/class_info.json) /
[`relation_info.json`](output/mario/relation_info.json)) was hand-customized
from PyGraft's own auto-generated schema
([`generated_schema.rdf`](output/mario/generated_schema.rdf)) so that the
synthetic graph shares Mario's real class (`Character`) and relation names.
This makes the two graphs' relations directly comparable (see the rule
mining below) without needing any entity alignment.

Running PyGraft's KG generator against these files produces
[`output/mario/full_graph.rdf`](output/mario/full_graph.rdf), which the
notebook then parses down to entity-to-entity and `type` triples only, and
serializes as `pygraft.ttl`/`.tsv`/`.csv` for comparison against
`mario.tsv`.

## Comparing the graphs — `graph_comparison.ipynb`

Takes the paths to any two graph files (RDF or plain `.tsv`/`.csv` triples,
here the target and synthetic Mario graphs) and compares them on two levels:

**Structural metrics** (`compare_graphs`): in/out-degree (from the raw
triples), and edges/triangles/clustering coefficient computed on a simple
undirected projection of the graph, including a multiplicity-weighted
edge-triangle count that accounts for parallel relations between the same
pair of entities. See the notebook's markdown cells for exact definitions.

**Global/logical metrics** (`compare_rules`): both graphs are run through
AMIE3 (via [`run_amie.py`](run_amie.py)) to mine Horn rules such as
`?a servantOf ?b => ?a allyOf ?b`. Since both graphs share the same relation
names, mined rule *patterns* (canonicalized by variable order, so equivalent
patterns compare equal) are directly comparable between the two graphs.
`compare_rules` outer-joins both rule sets on their canonical pattern and
reports shared vs. unique patterns, Jaccard similarity, and each side's head
coverage/confidence/support side by side.

### Findings (see the notebook for full discussion)

- The two graphs are structurally close (same entity count, similar degree
  distributions and clustering), though the real graph's degree distribution
  is noticeably more skewed (hub-like) than PyGraft's, which spreads triples
  more evenly across entities.
- Logically, the real graph encodes actual rule structure AMIE can recover
  (e.g. a servant is always also counted as an ally) that the synthetic
  graph does not reproduce at all once trivial `type`-inference rules are
  excluded — PyGraft's schema-driven generation captures relation-level
  statistics but not this kind of cross-relation logical dependency.

## `run_amie.py`

A thin CLI wrapper around AMIE3, invoked as a Java subprocess:

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
small — pass `--mins 1 --minis 1 --minhc 0` (and optionally `--minc 0
--minpca 0`) as shown above. Run `python run_amie.py --help` for all options.

## Setup

**Python dependencies**: `networkx`, `numpy`, `pandas`, `rdflib`, `pygraft`,
plus Jupyter to run the notebooks. There is currently no pinned
requirements/environment file in this repo.

**AMIE3**: `run_amie.py` shells out to a local AMIE3 `.jar` (default:
`amie3.5.1.jar` next to the script, override with `--jar`). It requires a
Java runtime on `PATH`. Download AMIE3 from the
[AMIE repository](https://github.com/dig-team/amie) — `*.jar` files are
git-ignored here and not checked in.

**AMIE/ and pygraft/ directories**: these are vendored, git-ignored copies
of the two upstream projects' full source (used for reference/local
development, e.g. `AMIE/inference` scripts and building AMIE from source).
They aren't required to run the notebooks — only the AMIE3 jar and the
`pygraft` Python package are — and aren't included when this repo is cloned.
Obtain them separately from
[dig-team/amie](https://github.com/dig-team/amie) and
[nicolas-hbt/pygraft](https://github.com/nicolas-hbt/pygraft) if you need
them.
