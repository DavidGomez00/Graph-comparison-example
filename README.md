# Graph analysis and comparison

Tools and notebooks for generating a synthetic knowledge graph (KG) with
[PyGraft](https://github.com/nicolas-hbt/pygraft) from a hand-authored or
real-world target graph, and for comparing the two graphs both structurally
(degree, triangles, clustering) and logically (Horn rules mined with
[AMIE3](https://github.com/dig-team/amie)).

**How well does a schema-driven synthetic KG generator
reproduce the structural and logical properties of a real, hand-curated graph
that shares its schema?**

Two target graphs are worked through here: a small hand-authored "Mario"
universe of characters and their relations, and a much larger real-world
extract of French royalty from DBpedia. A PyGraft schema hand-crafted is 
made to match the target graph's own classes and relations (rather than 
PyGraft's generic `C1`/`R1` names), then a synthetic KG generated from 
that schema for comparison.

## The target graphs

### Super Mario

[`public_data/mario.tsv`](public_data/mario.tsv) is a small, hand-authored
knowledge graph: 14 entities (Mario, Luigi, Bowser, Peach, ...), all typed
`Character`, connected by 119 triples over 5 relations. It exists purely as a
non-trivial but easy-to-inspect "ground truth" graph to generate a synthetic
counterpart from and compare against.

### French royalty

[`.data/french_royalty/french_royalty_no_literals.tsv`](.data/french_royalty/french_royalty_no_literals.tsv)
is a real-world extract from DBpedia: 4429 entities, 2212 of them explicitly
typed `Person` (the rest only ever appear as the subject/object of a
relation, a completeness artifact of the source extraction, not a modeling
choice), connected by 6442 relation triples over 8 relations (`child`,
`parent`, `spouse`, `father`, `mother`, `successor`, `predecessor`,
`marriedTo`; counts range from 1897 for `child` down to 20 for `marriedTo`).
The file also carries 10 `rdf:type rdf:Property` declarations for the
relations themselves (plus two, `name`/`gender`, for literal-valued
predicates that were stripped when producing the `_no_literals` file).
These are ontology bookkeeping, not instance data, and aren't reproduced.

## Generating the synthetic graphs

[PyGraft](https://github.com/nicolas-hbt/pygraft) generates a synthetic KG
from a schema plus a set of numeric parameters. Rather than let PyGraft invent
generic class/relation names (`C1`, `R1`, ...), each target graph gets a schema 
hand-customized from PyGraft's own auto-generated one, so that the synthetic
graph shares the target's real class and relation names. This makes the two 
graphs' relations directly comparable without needing any entity alignment.

### Mario schema

Configured in [`mario.yml`](mario.yml). The schema in
[`output/mario/schema.rdf`](output/mario/schema.rdf) (and its matching
[`class_info.json`](output/mario/class_info.json) /
[`relation_info.json`](output/mario/relation_info.json)) was hand-customized
from PyGraft's own auto-generated schema
([`generated_schema.rdf`](output/mario/generated_schema.rdf)): the one class
(`Character`) and 5 relations (`brotherOf`, `servantOf`, `allyOf`, `enemyOf`,
`loves`, all domain/range `Character`) were renamed to their real Mario
names, `brotherOf` was made symmetric to match the data. A second, inert 
`PlaceholderClass` was kept only because PyGraft requires at least 2 classes 
to run; it is never assigned to any instance.

Running PyGraft's KG generator against these files produces
[`output/mario/full_graph.rdf`](output/mario/full_graph.rdf), which the
notebook then parses down to entity-to-entity and `type` triples only, and
serializes as `pygraft.ttl`/`.tsv`/`.csv` for comparison against
`mario.tsv`.

### French royalty schema

Configured in [`french_royalty.yml`](french_royalty.yml). The schema in
[`output/french_royalty/schema.rdf`](output/french_royalty/schema.rdf) (and
its matching
[`class_info.json`](output/french_royalty/class_info.json) /
[`relation_info.json`](output/french_royalty/relation_info.json)) was built
the same way as Mario's, this time modeling one real class (`Person`, plus
the same inert `PlaceholderClass`) and the 8 real relations, all
domain/range `Person`, with characteristics inferred from what the relation
names actually mean:

- `parent` / `child`: inverses of each other (`owl:inverseOf`)
- `father` / `mother`: `rdfs:subPropertyOf parent`
- `spouse`: `owl:SymmetricProperty`
- `marriedTo`: also `owl:SymmetricProperty`, and `rdfs:subPropertyOf spouse`
  (it's a much rarer synonym in the data, 20 triples vs. spouse's 1152)
- `successor` / `predecessor`: inverses of each other

All 8 are irreflexive. Running PyGraft's KG generator against these files
(`pygraft.generate_kg("french_royalty.yml")`) produces
[`output/french_royalty/full_graph.rdf`](output/french_royalty/full_graph.rdf),
a logically consistent KG with all 4429 entities and all 8 relations
represented. It's parsed down to `.data/french_royalty/pygraft.tsv`/`.ttl`
the same way Mario's is (see `pygraft_generation.ipynb`), but not yet copied
to `public_data/` or run through `graph_comparison.ipynb`.

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

### The synthetic graph's own schema relationships don't show up in the data

`output/french_royalty/schema.rdf` declares `parent`/`child` and
`successor`/`predecessor` as inverses, `father`/`mother` as subproperties of
`parent`, `marriedTo` as a subproperty of `spouse`, and `spouse`/`marriedTo`
as symmetric. None of these hold in the generated instance data. Checking
`output/french_royalty/full_graph.rdf` directly, for every entity pair
`(a, b)`:

```
parent triples: 542, child triples: 1047, parent(a,b) with matching child(b,a): 0
successor: 1281, predecessor: 1971, successor(a,b) with matching predecessor(b,a): 0
father: 1984, parent: 542, father(a,b) also present as parent(a,b): 0
marriedTo: 1468, spouse: 1432, marriedTo(a,b) also present as spouse(a,b): 0
spouse: 1432 (declared symmetric), (a,b) with (b,a) also present: 0
```

PyGraft's `fast_gen` instance generator only uses these declarations to
check that the resulting graph is not logically contradictory. It does not
use them to actually generate matching triples. Each relation's entity
pairs are sampled independently at random, constrained only by domain,
range, and the per-relation triple budget from `relation_balance_ratio`. 

## Comparing the graphs

Currently run for Mario only ([`graph_comparison.ipynb`](graph_comparison.ipynb));
the French royalty synthetic graph is generated
(`output/french_royalty/full_graph.rdf`) and parsed to
`.data/french_royalty/pygraft.tsv`, but hasn't been copied to `public_data/`
or run through this notebook yet. Takes the paths to any two graph files
(RDF or plain `.tsv`/`.csv` triples, here the target and synthetic Mario
graphs) and compares them on
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
- Running `run_amie.py` on `.data/french_royalty/pygraft.tsv` at AMIE's 
  default thresholds (`-mins 100`, `-minhc 0.01`) mines 0 rules, and that's
  the correct answer given the data: there is nothing above chance for AMIE
  to find. Loosening the thresholds (`--mins 1 --minis 1 --minhc 0`) does
  produce around 60 candidate rules, but every one has `positive_examples: 1`
  and `head_coverage` under 0.002, a single coincidental overlap out of
  thousands of triples, not real structure. This is the same limitation already
  noted for Mario, confirmed here with a schema that has four explicit logical 
  relationships to check against instead of one: PyGraft's schema-driven 
  generation reproduces relation-level statistics (how many triples per relation, 
  which classes they connect) but not the cross-relation logical dependencies its
  own schema declares.


See [`getting started.md`](Getting started.md) to run the code yourself.