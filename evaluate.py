"""
Rank multiple synthetic-graph-generation methods against one target graph in
a single wide table.

Every other report in this repo (`topology_report.py`, `kernel_report.py`)
compares exactly one real/synthetic pair per run. This orchestrates them
across N synthetic methods (e.g. `pygraft` vs. `skgg`) against the same
target, so their metrics can be read side by side instead of diffed by hand
across separate CSV files.
"""

from pathlib import Path

import pandas as pd

from kernel_report import weisfeiler_lehman_similarity
from topology_report import (
    calculate_distribution_divergence,
    calculate_js_divergence,
    calculate_local_clustering,
    calculate_pagerank,
    calculate_predicate_js_divergence,
    calculate_spectral_distance,
    calculate_structural_metrics,
    count_predicate_pairs,
    load_graph_tsv,
)


def evaluate_method(target_file, target_graph, method_file, exclude_predicates=None):
    """
    Compute every comparison metric for one target-vs-synthetic pair.

    Reuses `topology_report.py`'s and `kernel_report.py`'s individual
    `calculate_*` functions directly rather than going through
    `topology_report()`/`kernel_report()` (which each write their own CSV) --
    `evaluate_method` only needs the metric dict, assembled by the caller
    into one row per method instead of one file per method.

    Args:
        target_file: Path to the target graph's TSV edge-list file (only
            used for the predicate-count JS-divergence, which reads raw
            triples rather than the loaded graph).
        target_graph: The target graph, already loaded via `load_graph_tsv`
            (passed in so it's only loaded once across every method compared
            against it).
        method_file: Path to this method's synthetic graph TSV.
        exclude_predicates: Optional iterable of predicate/relation labels
            to leave out of every measurement (see `load_graph_tsv`).

    Returns:
        A dict of metric name -> value for this target/method pair.
    """
    method_graph = load_graph_tsv(method_file, exclude_predicates=exclude_predicates)

    structural = calculate_structural_metrics(method_graph)

    predicate_counts_target = count_predicate_pairs(
        target_file, exclude_predicates=exclude_predicates
    )
    predicate_counts_method = count_predicate_pairs(
        method_file, exclude_predicates=exclude_predicates
    )

    pagerank_target = calculate_pagerank(target_graph)
    pagerank_method = calculate_pagerank(method_graph)
    pagerank_divergence = calculate_distribution_divergence(pagerank_target, pagerank_method)

    clustering_target = calculate_local_clustering(target_graph)
    clustering_method = calculate_local_clustering(method_graph)
    clustering_divergence = calculate_distribution_divergence(clustering_target, clustering_method)

    return {
        "nodes": method_graph.number_of_nodes(),
        "edges": method_graph.number_of_edges(),
        "undirected_edges": structural["undirected_edges"],
        "node_triangles": structural["node_triangles"],
        "edge_triangles": structural["edge_triangles"],
        "clustering_coefficient": structural["clustering_coefficient"],
        "average_clustering": float(clustering_method.mean()),
        "max_in_degree": structural["max_in_degree"],
        "max_out_degree": structural["max_out_degree"],
        "std_in_degree": structural["std_in_degree"],
        "std_out_degree": structural["std_out_degree"],
        "js_divergence_in_degree": calculate_js_divergence(target_graph, method_graph, "in"),
        "js_divergence_out_degree": calculate_js_divergence(target_graph, method_graph, "out"),
        "js_divergence_pairs_per_predicate": calculate_predicate_js_divergence(
            predicate_counts_target, predicate_counts_method
        ),
        "js_divergence_pagerank": pagerank_divergence["js_divergence"],
        "wasserstein_pagerank": pagerank_divergence["wasserstein_distance"],
        "js_divergence_local_clustering": clustering_divergence["js_divergence"],
        "wasserstein_local_clustering": clustering_divergence["wasserstein_distance"],
        "spectral_distance": calculate_spectral_distance(
            target_graph, method_graph, normalized=False
        ),
        "normalized_spectral_distance": calculate_spectral_distance(
            target_graph, method_graph, normalized=True
        ),
        "wl_similarity_h3": weisfeiler_lehman_similarity(target_graph, method_graph, h=3),
    }


def evaluate(target_file, methods, output_csv, exclude_predicates=None):
    """
    Compare a target graph against N synthetic methods and write a single
    wide report: one row per metric, one column per method.

    Args:
        target_file: Path to the target graph's TSV edge-list file.
        methods: Dict of method name -> path to that method's synthetic
            graph TSV, e.g. `{"pygraft": ..., "skgg": ...}`.
        output_csv: Path to write the CSV report to (also written as
            Markdown, alongside it with a `.md` extension). Parent
            directories are created as needed; existing files at these
            paths are overwritten.
        exclude_predicates: Optional iterable of predicate/relation labels
            to leave out of every measurement (see `load_graph_tsv`).

    Returns:
        The resulting `pandas.DataFrame` (rows = metric, columns = method).
    """
    target_graph = load_graph_tsv(target_file, exclude_predicates=exclude_predicates)

    columns = {
        method_name: evaluate_method(
            target_file, target_graph, method_file, exclude_predicates=exclude_predicates
        )
        for method_name, method_file in methods.items()
    }
    df = pd.DataFrame(columns)
    df.index.name = "metric"

    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path)
    output_path.with_suffix(".md").write_text(df.to_markdown())

    return df


if __name__ == "__main__":
    # Replace these paths with your own files
    target_file = "data/french_royalty/normalized/french_royalty.tsv"
    methods = {
        "pygraft": "data/french_royalty/pygraft/french_royalty.tsv",
        "skgg": "data/french_royalty/skgg/french_royalty.tsv",
    }
    output_csv = "output/french_royalty/evaluation.csv"

    # Predicates to leave out of every measurement below
    exclude_predicates = {"type"}

    result = evaluate(
        target_file=target_file,
        methods=methods,
        output_csv=output_csv,
        exclude_predicates=exclude_predicates,
    )
    print(result)
