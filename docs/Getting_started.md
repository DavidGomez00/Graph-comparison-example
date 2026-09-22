# Setup

Use `pip install -r requirements.txt` to install the necessary dependencies.

Every script below reads TSV edge-list files: three tab-separated columns per line, `Source  Predicate  Target`, no header row. `data/french_royalty/` ships four variants of the same graph (see the main [`README.md`](../README.md)) and is what every example on this page uses -- swap in your own files by path wherever they appear.

# Running the comparison reports

None of `topology_report.py`, `kernel_report.py`, `rule_report.py`, `evaluate.py`, and `graphml_export.py` take command-line arguments. Each ends with an `if __name__ == "__main__":` block that calls its main function with a small set of example paths -- open the script, edit those paths (and `exclude_predicates`, if you want to drop a relation like `type` before computing metrics), and run it directly, e.g.:

```bash
python topology_report.py
```

This writes CSV report(s) to the `output_csv` path given in that block (parent directories are created automatically). You can also import and call the underlying function yourself instead of editing the file, e.g. from a notebook:

```python
from topology_report import topology_report

topology_report(
    real_file="data/french_royalty/source/french_royalty.tsv",
    synthetic_file="data/french_royalty/pygraft/french_royalty.tsv",
    output_csv="output/french_royalty/topology_report.csv",
    exclude_predicates={"type"},
)
```

## Structural comparison: `topology_report.py`

Compares a "real"/target graph against a "synthetic" one on spectral distance, degree/predicate JS-divergence, triangle/clustering/degree structural metrics, and PageRank/local-clustering distributions. See the module's docstring and [`README.md`](../README.md#comparing-the-graphs) for what each metric means.

```bash
python topology_report.py
```

writes `output/french_royalty/topology_report.csv` from the paths at the bottom of the file:

```python
real_file = "data/french_royalty/source/french_royalty.tsv"
synthetic_file = "data/french_royalty/pygraft/french_royalty.tsv"
output_csv = "output/french_royalty/topology_report.csv"
exclude_predicates = {"type"}
```

## Neighborhood-shape comparison: `kernel_report.py`

Computes the normalized Weisfeiler-Lehman subtree kernel similarity between the two graphs at a few neighborhood-hop depths (`h_values`) -- catches cases where two graphs match on every `topology_report.py` summary statistic but still have differently-shaped local neighborhoods.

```bash
python kernel_report.py
```

writes `output/french_royalty/kernel_report.csv`.

## Logical/rule-based comparison: `run_amie.py` + `rule_report.py`

This comparison needs rules mined from *each* graph first, then diffed.

1. Mine rules from each graph individually with `run_amie.py` (needs a Java runtime on `PATH`; download AMIE3 from the [AMIE repository](https://github.com/dig-team/amie) or use the `amie3.5.1.jar` already in this repo):

   ```bash
   python run_amie.py data/french_royalty/normalized/french_royalty.tsv -o output/french_royalty/normalized_rules.csv

   python run_amie.py data/french_royalty/pygraft/french_royalty.tsv -o output/french_royalty/pygraft_rules.csv
   ```

   > Note: AMIE's own defaults (`-mins`/`-minis` 100, `-minhc` 0.01) are tuned for large knowledge bases and will silently mine zero (or only trivial) rules on a small or logically-thin graph like this one -- pass `--mins 1 --minis 1 --minhc 0` (and optionally `--minc 0 --minpca 0` to stop AMIE filtering by confidence too), then judge by `head_coverage`/`positive_examples` whether what comes back is real structure. Run `python run_amie.py --help` for every option.

2. Compare the two resulting rule CSVs with `rule_report.py`:

   ```bash
   python rule_report.py
   ```

   writes `output/french_royalty/rule_summary.csv` (shared vs. unique rule counts, Jaccard similarity) and `output/french_royalty/rule_comparison.csv` (one row per distinct rule pattern, with each side's head_coverage/confidence/support side by side), from the paths at the bottom of the file -- edit those to point at the two rule CSVs you just produced.

## Multiple synthetic methods vs. one target: `evaluate.py`

Runs every metric from `topology_report.py` and `kernel_report.py` across N synthetic methods against the same target graph, as one wide table (one row per metric, one column per method) instead of one CSV per pairwise run.

```bash
python evaluate.py
```

writes `output/french_royalty/evaluation.csv` and `.md`, from:

```python
target_file = "data/french_royalty/normalized/french_royalty.tsv"
methods = {
    "pygraft": "data/french_royalty/pygraft/french_royalty.tsv",
    "skgg": "data/french_royalty/skgg/french_royalty.tsv",
}
```

Add more entries to `methods` to compare additional generation methods in the same run.

## Visual inspection: `graphml_export.py`

Exports a graph as GraphML with PageRank precomputed as a node attribute, for loading into [Cytoscape](https://cytoscape.org/) (map node size/color to `pagerank` for a quick sanity check of which graph has more realistic hubs).

```bash
python graphml_export.py
```

writes one `.graphml` file per `export_graphml(...)` call at the bottom of the file.
