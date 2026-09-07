# Graph analysis and comparison

Tools and notebooks for generating a synthetic knowledge graph (KG) with
[PyGraft](https://github.com/nicolas-hbt/pygraft) from a hand-authored or
real-world target graph, and for comparing the two graphs both structurally
(degree, triangles, clustering) and logically (Horn rules mined with
[AMIE3](https://github.com/dig-team/amie)).

The guiding question: how well does a schema-driven synthetic KG generator
reproduce the structural and logical properties of a real, hand-curated graph
that shares its schema?

Two target graphs are worked through here: a small hand-authored "Mario"
universe of characters and their relations, and a much larger real-world
extract of French royalty from DBpedia. Both get the same treatment: a
PyGraft schema hand-crafted to match the target graph's own classes and
relations (rather than PyGraft's generic `C1`/`R1` names), then a synthetic
KG generated from that schema for comparison.

## Repository layout

```
.
├── mario.yml                      # PyGraft config for Mario: schema + KG generation parameters
├── french_royalty.yml             # PyGraft config for French royalty: schema + KG generation parameters
├── pygraft_generation.ipynb       # Generates the synthetic KG with PyGraft
├── graph_comparison.ipynb         # Compares target vs. synthetic graph
├── run_amie.py                    # CLI wrapper: run AMIE3 and export mined rules to CSV
├── output/mario/                  # Hand-crafted PyGraft schema + PyGraft's generated KG (Mario)
│   ├── schema.rdf                 #   hand-customized schema (classes/relations named for Mario)
│   ├── generated_schema.rdf       #   PyGraft's auto-generated schema, kept for reference
│   ├── class_info.json            #   class hierarchy fed to PyGraft's KG generator
│   ├── relation_info.json         #   relation characteristics fed to PyGraft's KG generator
│   ├── kg_info.json               #   PyGraft's report on the KG it generated
│   └── full_graph.rdf             #   the synthetic KG PyGraft generated (RDF/XML)
├── output/FR/                     # Hand-crafted PyGraft schema + PyGraft's generated KG (French royalty)
│   ├── schema.rdf                 #   hand-customized schema (classes/relations named for the real data)
│   ├── generated_schema.rdf       #   PyGraft's auto-generated schema, kept for reference
│   ├── class_info.json            #   class hierarchy fed to PyGraft's KG generator
│   ├── relation_info.json         #   relation characteristics fed to PyGraft's KG generator
│   ├── kg_info.json               #   PyGraft's report on the KG it generated
│   └── full_graph.rdf             #   the synthetic KG PyGraft generated (RDF/XML)
├── public_data/                   # Target and synthetic graphs as plain triples, checked in
│   ├── mario.tsv / mario.csv      #   Mario target graph (hand-authored)
│   └── pygraft.tsv / pygraft.csv  #   Mario synthetic graph (parsed from output/mario/full_graph.rdf)
├── .data/mario/                   # Local working copy of the Mario data (git-ignored)
├── .data/french_royalty/          # Local working copy of the French royalty data (git-ignored)
│   └── french_royalty_no_literals.tsv  # target graph: a DBpedia French royalty extract, literals stripped
├── amie3.5.1.jar                  # AMIE3 jar used by run_amie.py (git-ignored, not checked in)
├── AMIE/                          # Vendored copy of the AMIE rule-mining engine (git-ignored)
└── pygraft/                       # Vendored copy of the PyGraft KG generator (git-ignored)
```

`AMIE/` and `pygraft/` are separate upstream projects tracked in this working
copy as plain directories (not real git submodules), and both are git-ignored. They are not part of this repo's
history and are not published with it; see below for how to obtain them.

## The target graphs

### Mario

[`public_data/mario.tsv`](public_data/mario.tsv) is a small, hand-authored
knowledge graph: 14 entities (Mario, Luigi, Bowser, Peach, ...), all typed
`Character`, connected by 119 triples over 5 relations. It exists purely as a
non-trivial but easy-to-inspect "ground truth" graph to generate a synthetic
counterpart from and compare against.

### French royalty

[`.data/french_royalty/french_royalty_no_literals.tsv`](.data/french_royalty/french_royalty_no_literals.tsv)
is a real-world extract from DBpedia: 4429 entities, 2212 of them explicitly
typed `Person` (the rest only ever appear as the subject/object of a
relation — a completeness artifact of the source extraction, not a modeling
choice), connected by 6442 relation triples over 8 relations (`child`,
`parent`, `spouse`, `father`, `mother`, `successor`, `predecessor`,
`marriedTo`; counts range from 1897 for `child` down to 20 for `marriedTo`).
The file also carries 10 `rdf:type rdf:Property` declarations for the
relations themselves (plus two, `name`/`gender`, for literal-valued
predicates that were stripped when producing the `_no_literals` file) —
these are ontology bookkeeping, not instance data, and aren't reproduced.

## Generating the synthetic graphs

[PyGraft](https://github.com/nicolas-hbt/pygraft) generates a synthetic KG
from a schema plus a set of numeric parameters (number of entities/triples,
relation properties such as symmetry/transitivity, class hierarchy depth,
etc.). Rather than let PyGraft invent generic class/relation names (`C1`,
`R1`, ...), each target graph gets a schema hand-customized from PyGraft's
own auto-generated one, so that the synthetic graph shares the target's real
class and relation names — making the two graphs' relations directly
comparable (see the rule mining below) without needing any entity alignment.

### Mario schema

Configured in [`mario.yml`](mario.yml). The schema in
[`output/mario/schema.rdf`](output/mario/schema.rdf) (and its matching
[`class_info.json`](output/mario/class_info.json) /
[`relation_info.json`](output/mario/relation_info.json)) was hand-customized
from PyGraft's own auto-generated schema
([`generated_schema.rdf`](output/mario/generated_schema.rdf)): the one class
(`Character`) and 5 relations (`brotherOf`, `servantOf`, `allyOf`, `enemyOf`,
`loves`, all domain/range `Character`) were renamed to their real Mario
names, `brotherOf` was made symmetric to match the data, and PyGraft's one
spurious `rdfs:subPropertyOf` (a library artifact, not a real characteristic
of the data) was dropped. A second, inert `PlaceholderClass` was kept only
because PyGraft requires at least 2 classes to run; it is never assigned to
any instance.

Running PyGraft's KG generator against these files produces
[`output/mario/full_graph.rdf`](output/mario/full_graph.rdf), which the
notebook then parses down to entity-to-entity and `type` triples only, and
serializes as `pygraft.ttl`/`.tsv`/`.csv` for comparison against
`mario.tsv`.

### French royalty schema

Configured in [`french_royalty.yml`](french_royalty.yml). The schema in
[`output/FR/schema.rdf`](output/FR/schema.rdf) (and its matching
[`class_info.json`](output/FR/class_info.json) /
[`relation_info.json`](output/FR/relation_info.json)) was built the same way
as Mario's, this time modeling one real class (`Person`, plus the same inert
`PlaceholderClass`) and the 8 real relations, all domain/range `Person`,
with characteristics inferred from what the relation names actually mean:

- `parent` / `child` — inverses of each other (`owl:inverseOf`)
- `father` / `mother` — `rdfs:subPropertyOf parent`
- `spouse` — `owl:SymmetricProperty`
- `marriedTo` — also `owl:SymmetricProperty`, and `rdfs:subPropertyOf spouse`
  (it's a much rarer synonym in the data: 20 triples vs. spouse's 1152)
- `successor` / `predecessor` — inverses of each other

All 8 are irreflexive. Running PyGraft's KG generator against these files
(`pygraft.generate_kg("french_royalty.yml")`) produces
[`output/FR/full_graph.rdf`](output/FR/full_graph.rdf), a logically
consistent KG with all 4429 entities and all 8 relations represented (not
yet parsed down to `public_data/`/compared the way Mario's is — see
`pygraft_generation.ipynb` for that step on Mario).

Two aspects of the real data don't survive the round-trip, documented as
comments in `french_royalty.yml`:

1. **Untyped-but-connected entities.** In the real data, ~50% of entities
   are never given an explicit `type Person` triple, yet still appear in
   relations. PyGraft can't reproduce that when every relation's domain and
   range is `Person`: entities without that type are simply never drawn to
   fill such a relation, so leaving them "untyped" just makes them vanish
   from the graph entirely rather than appear untyped-but-connected. The
   config instead types all 4429 entities (`prop_untyped_entities: 0.0`),
   trading a larger `type` triple count (4429 vs. the real 2212) for a
   synthetic graph that actually uses its full declared entity pool.
2. **Relation imbalance.** Real per-relation counts are highly skewed
   (`child` is ~95x `marriedTo`). PyGraft spreads triples across relations
   as random weights of magnitude `1 - relation_balance_ratio`; empirically,
   anything below ~0.7 has a non-trivial chance of zeroing a relation out
   entirely across only 8 buckets. `relation_balance_ratio: 0.7` is the
   lowest value that reliably (0/200 trial runs) keeps all 8 relations
   present, at the cost of a milder imbalance than the real data's.

## Comparing the graphs

Currently run for Mario only ([`graph_comparison.ipynb`](graph_comparison.ipynb));
the French royalty synthetic graph is generated (`output/FR/full_graph.rdf`)
but hasn't been parsed down to `public_data/` or run through this notebook
yet. Takes the paths to any two graph files (RDF or plain `.tsv`/`.csv`
triples, here the target and synthetic Mario graphs) and compares them on
two levels:

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
  excluded. PyGraft's schema-driven generation captures relation-level
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
small. Pass `--mins 1 --minis 1 --minhc 0` (and optionally `--minc 0
--minpca 0`) as shown above. Run `python run_amie.py --help` for all options.

## Setup

**Python dependencies**: `networkx`, `numpy`, `pandas`, `rdflib`, `pygraft`,
plus Jupyter to run the notebooks. There is currently no pinned
requirements/environment file in this repo.

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
