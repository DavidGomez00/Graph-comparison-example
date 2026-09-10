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

### Office schema

[`data/office.ttl`](data/office.ttl) is a small hand-authored target graph: 5
entities (3 `Person` -- Alice, Bob, Charlie --, 1 `Organization`, 1 `Project`)
connected by 10 relation triples over 4 relations (`knows`, `works_for`,
`assignedTo`, `reportsTo`). Configured in
[`data/office.yml`](data/office.yml). The schema in
[`output/office/schema.rdf`](output/office/schema.rdf) (and its matching
[`class_info.json`](output/office/class_info.json) /
[`relation_info.json`](output/office/relation_info.json)) was hand-customized
the same way as Mario's and French royalty's: 3 real classes (`Person`,
`Organization`, `Project`, all flat direct subclasses of `owl:Thing` -- no
`PlaceholderClass` needed here, since 3 real classes already satisfies
PyGraft's minimum) and the 4 real relations, with characteristics inferred
from what they mean: `knows` is `owl:SymmetricProperty` +
`owl:IrreflexiveProperty` (domain/range both `Person`), `reports_to` is
`owl:AsymmetricProperty` (domain/range both `Person`), `works_for` is
`Person` -> `Organization`, `assigned_to` is `Person` -> `Project`.

Two details worth calling out for anyone hand-crafting a schema this small:

- **`class_info.json`'s hierarchy dictionaries must be fully populated, not
  left as placeholders.** `pygraft.generate_kg`'s `assign_most_specific` reads
  `class_info["layer2classes"][layer]` directly and raises `KeyError`
  immediately if it's empty. Since all 3 office classes are flat (no
  subclassing, `class_inheritance_ratio: 0.0`), they all belong to a single
  layer: `hierarchy_depth: 1`, `layer2classes: {"1": ["Person",
  "Organization", "Project"]}`, and so on for `class2layer` /
  `direct_class2subclasses` / `direct_class2superclass` /
  `transitive_class2subclasses` / `transitive_class2superclasses` (see
  `output/office/class_info.json`).
- **`num_triples` in the `.yml` config counts relation triples only** --
  `pygraft`'s own `self.kg` semantics, confirmed against `mario.yml`'s
  `num_triples: 119` matching the relation-only triple count quoted for Mario
  above. `rdf:type` triples are added separately by `generate_kg`, one per
  typed entity, on top of that count. `office.ttl` has 15 triples in total,
  but only 10 of them are relation triples (the other 5 are `rdf:type`), so
  `office.yml` sets `num_triples: 10`, not 15.

Running `python run_pygraft.py` (see "Running PyGraft" below) calls
`pygraft.generate_kg("data/office.yml")`, producing
[`output/office/full_graph.rdf`](output/office/full_graph.rdf) and
`output/office/kg_info.json`, then parses the result down to
`data/office/office_pygraft.ttl`/`.tsv` the same way Mario's is.

With only 5 entities randomly typed across 3 classes (PyGraft samples each
entity's specific class uniformly at random within its layer -- there's no
way to bias it towards office.ttl's real 3:1:1 split), a run has a
non-trivial chance of leaving a class or a relation completely empty (e.g. no
entity drawn `Organization`, so `works_for` never fires), and
`generate_triples` gives up for good after 10 consecutive failed attempts
rather than retrying indefinitely. Re-running `python run_pygraft.py` a
handful of times until `output/office/kg_info.json` reports
`num_instantiated_relations: 4` (all relations used) reliably lands a full
reproduction -- this is a property of generating from such a small entity
pool, not a bug.

### Running PyGraft

PyGraft (and this repo's other Python dependencies) are installed in the
`NeSy` pyenv virtualenv, not the system interpreter -- see "Setup" in
[`Getting_started.md`](Getting_started.md) for the exact interpreter path and
a footgun worth knowing about.

[`run_pygraft.py`](run_pygraft.py) drives a single schema end to end:

```bash
~/.pyenv/versions/NeSy/bin/python run_pygraft.py
```

It sets `schema_name` at the top of the file (currently `"office"`), calls
`pygraft.generate_kg(f"data/{schema_name}.yml")`, then uses
[`utils.py`](utils.py)'s `parse_result` to filter `output/<schema_name>/full_graph.rdf`
down to entity-to-entity and `rdf:type` triples only, serialized as
`data/<schema_name>/<schema_name>_pygraft.ttl`/`.tsv` for comparison against
the target graph. To generate a different schema, change `schema_name` (a
config `data/<name>.yml` and hand-crafted `output/<name>/{schema.rdf,
class_info.json, relation_info.json}` must already exist -- see the recipe
below).

### Hand-crafting a PyGraft schema for a new target graph

Mario, French royalty, and Office all follow the same recipe for turning a
target graph into a comparable synthetic one:

1. Count the target graph's classes, distinct relations, entities, and
   relation triples (i.e. everything except `rdf:type` triples).
2. Write `data/<name>.yml` from PyGraft's own template
   (`pygraft.create_template()`, vendored here as
   [`data/template.yml`](data/template.yml)), setting `schema_name` and
   `num_classes`/`num_relations`/`num_entities` to the real counts,
   `num_triples` to the real **relation-triple** count (not the total --
   `generate_kg` adds one `rdf:type` triple per typed entity on top of this),
   and the `prop_*_relations` fields to `count / num_relations` for each OWL
   characteristic actually present in the target data.
3. Hand-write `output/<name>/schema.rdf` (OWL classes + `owl:ObjectProperty`
   declarations with real domain/range and characteristics), matching the
   target's real predicate semantics. If there's only 1 real class, add an
   inert second `PlaceholderClass` (see Mario/French royalty) -- PyGraft
   requires at least 2.
4. Hand-write `output/<name>/class_info.json` -- the two most common
   mistakes: `hierarchy_depth` must equal the *actual* deepest populated
   layer (not the `max_hierarchy_depth` config ceiling), and
   `layer2classes`/`class2layer`/`direct_class2subclasses`/`direct_class2superclass`/
   `transitive_class2subclasses`/`transitive_class2superclasses` must never be
   left as empty placeholders -- `generate_kg` reads them directly and
   `KeyError`s immediately if they don't cover every class. A flat,
   non-hierarchical schema (all classes direct children of `owl:Thing`) is
   layer `1` for every class, `hierarchy_depth: 1`.
5. Hand-write `output/<name>/relation_info.json` -- `relations`, `rel2dom`,
   `rel2range`, `rel2patterns`, the per-characteristic lists
   (`symmetric_relations`, `asymmetric_relations`, etc.), `rel2inverse`,
   `rel2superrel`, and a `statistics` block whose `prop_*` fields equal
   `len(list) / num_relations` (PyGraft's own formula, see
   `relation_generator.py`'s `assemble_relation_info`) -- keep it consistent
   with the lists, even though `generate_kg` itself never reads `statistics`.
6. Set `schema_name` in `run_pygraft.py` to `<name>` and run it (see "Running
   PyGraft" above). Confirm the "Consistent KG" message and
   `output/<name>/{full_graph.rdf,kg_info.json}`. For a small entity pool,
   `output/<name>/kg_info.json`'s `statistics.num_instantiated_relations` may
   come up short of the schema's real relation count on a given run (see
   "Office schema" above) -- just re-run until it doesn't.
7. Compare structurally against the target file (entity/class/relation
   counts, and optionally `topologic_similarity.py` after converting both to
   TSV) -- PyGraft always names synthetic entities generically (`E1`, `E2`,
   ...), so this is a structural/statistical match, not a literal
   triple-for-triple copy.

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
Like `compare_rules` below, `compare_graphs` (and the underlying
`load_triples`/`graph_metrics`) takes an `exclude_predicates` argument: any
triple using one of those predicates is dropped before the metrics are
computed. Pass `{"type"}` to ignore "a type b" relations, which are often
irrelevant since these graphs only have one type.

**Global/logical metrics** (`compare_rules`): both graphs are run through
AMIE3 (via [`run_amie.py`](run_amie.py)) to mine Horn rules such as
`?a servantOf ?b => ?a allyOf ?b`. Since both graphs share the same relation
names, mined rule *patterns* (canonicalized by variable order, so equivalent
patterns compare equal) are directly comparable between the two graphs.
`compare_rules` outer-joins both rule sets on their canonical pattern and
reports shared vs. unique patterns, Jaccard similarity, and each side's head
coverage/confidence/support side by side. It takes the same
`exclude_predicates` argument, dropping any mined rule that uses one of
those predicates anywhere in its body or head; `type` rules dominate AMIE's
output (mostly "neighbor's type ⇒ own type"), so `exclude_predicates={"type"}`
is a quick way to zoom in on the rules relating the KG's "real" relations to
each other instead.

## Findings

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


See [`getting started.md`](Getting_started.md) to run the code yourself.