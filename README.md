# Graph analysis and comparison

Tools for comparing knowledge graphs (KGs) both structurally and logically (Horn rules mined with [AMIE3](https://github.com/dig-team/amie)).

## Available graphs

### French royalty

Add a summary for French Royalty dataset.

`data/french_royalty/` holds four variants of this same graph:

- `source/`: Original extract `source/french_royalty.pre-corrections.tsv` and non-literal version at `source/french_royalty.tsv`.
- `normalized/french_royalty.tsv`: Normalized graph generated from the non-literal version of French Royalty. I was normalized using [VANILLA](add doi).
- `pygraft/french_royalty.tsv`: A synthetic graph generated from the real graph's schema by PyGraft.
- `skgg/french_royalty.tsv`: A synthetic graph generated from the real graph's schema by SKGG.

Naming-convention and URI-vs-bare-name differences between these variants are normalized away before comparison.

## Comparing the graphs

Each of the scripts below takes the paths to a "real"/target and a "synthetic" TSV edge-list file and takes an `exclude_predicates` argument: any triple using one of those predicates is dropped before the metrics are computed. Pass `{"type"}` to ignore "a type b" relations, which are often irrelevant since these graphs only have one type.

[`topology_report.py`](topology_report.py) writes a CSV report comparing the two graphs on five axes:

- **Spectral distance**: Euclidean distance between the sorted eigenvalues of each graph's (normalized) Laplacian -- sensitive to global structure (connectivity, community structure) rather than individual node degrees.
- **JS-divergence (degrees)**: Jensen-Shannon divergence between the two graphs' in-/out-degree distributions.
- **JS-divergence (predicates)**: Jensen-Shannon divergence between how subject-object pairs are distributed across predicates. Predicate labels are shared vocabulary between a real graph and a synthetic one generated from its schema, so this captures whether each relation type is exercised proportionally as often in both.
- **Structural metrics**: undirected-projection edge count, node/edge triangles (the latter multiplicity-weighted, accounting for parallel relations between the same pair of entities), clustering coefficient, and max/std in-/out-degree, reported side by side (real vs. synthetic) rather than as a single similarity score. See the module's docstring and `calculate_structural_metrics` for exact definitions.
- **PageRank and local-clustering-coefficient distributions**: compared via both Jensen-Shannon divergence and Wasserstein distance. PageRank checks whether the two graphs create comparably realistic hub nodes; local clustering coefficient is the per-node distribution behind the single averaged `clustering_coefficient` scalar above, so two graphs with the same global transitivity but differently-shaped neighborhoods are told apart.

[`kernel_report.py`](kernel_report.py) computes the normalized Weisfeiler-Lehman (WL) subtree kernel similarity between the two graphs (via [GraKeL](https://ysig.github.io/GraKeL/)), at a few neighborhood-hop depths. Unlike the single-number summaries above, the WL kernel is sensitive to actual local neighborhood *shape*, so two graphs can match on every structural summary statistic while still scoring low here. 1.0 = identical structure, 0.0 = maximally dissimilar.

[`run_amie.py`](run_amie.py) mines Horn rules (e.g. `?a father ?b => ?a parent ?b`) from a single graph via AMIE3 and exports them to CSV. [`rule_report.py`](rule_report.py) then compares two such rule CSVs: mined rule *patterns* are canonicalized by variable order so equivalent patterns compare equal regardless of AMIE's internal naming, then
outer-joined on that canonical pattern to report shared vs. unique patterns, Jaccard similarity, and each side's head coverage/confidence/support side by side.

[`graphml_export.py`](graphml_export.py) exports a graph as GraphML with PageRank precomputed as a node attribute, for loading into [Cytoscape](https://cytoscape.org/) (map node size/color to `pagerank` for a quick visual sanity check).

[`evaluate.py`](evaluate.py) ranks multiple synthetic-generation methods against one target graph in a single wide table (one column per method, one row per metric from `topology_report.py` and `kernel_report.py`) -- e.g. `{"pygraft": ..., "skgg": ...}` against the French royalty target graph, written as both CSV and Markdown.

## Findings

- **Structurally**, French royalty's `pygraft/` synthetic graph diverges from the real `source/` graph more than it matches it: real clustering coefficient is ~10x higher (0.297 vs. 0.015 average), and the real graph's degree distribution is markedly more skewed/hub-like (max out-degree 27 vs. 18, std out-degree 4.48 vs. 2.77). PyGraft spreads
  triples more evenly across entities than the real data does.
- **Logically**, the real graph encodes real cross-relation structure AMIE recovers easily at its own default thresholds: `predecessor`/`successor` are exact inverses (confidence 1.0), `father(a,b) => parent(a,b)` holds for every single `father` triple (confidence 1.0), `spouse` is effectively symmetric (confidence 0.998) -- 118 non-trivial rules in total. Mining the `pygraft/` synthetic graph at the same default thresholds recovers *zero* non-trivial rules -- only 14 trivial `type`-inference rules (e.g. `?a mother ?f, ?f type ?b => ?a type ?b`). Loosening the thresholds (`--mins 1 --minis 1 --minhc 0 --minc 0 --minpca 0`) surfaces over a thousand candidate non-`type` rules, but every one has `positive_examples` in the single digits and `head_coverage` under 0.005 -- coincidental overlap out of thousands of triples, not real structure.
- Together, this says PyGraft's schema-driven generation reproduces relation-level statistics (how many triples per relation, which classes they connect) but not the cross-relation logical dependencies a schema like French royalty's actually has (inverse properties, subproperties, symmetry). `generate_kg`'s instance sampler only checks those declarations for logical consistency, it doesn't use them to generate matching triples.
- `evaluate.py` extends this same real-vs-synthetic comparison across multiple generation methods (`pygraft` vs. `skgg`) side by side against the same French royalty target, rather than one pairwise run at a time.

See [`Getting_started.md`](docs/Getting_started.md) to run the code yourself.
