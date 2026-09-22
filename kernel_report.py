"""
Weisfeiler-Lehman (WL) graph-kernel similarity between two graphs.

Complements `topology_report.py`'s single-number structural summaries
(spectral distance, degree/predicate JS-divergence, triangle counts, ...)
with a similarity measure sensitive to actual local *neighborhood patterns*
-- two graphs can match on every one of those summary statistics while still
having differently-shaped neighborhoods (e.g. the same degree sequence
arranged into different subgraphs), which the WL subtree kernel is
specifically designed to detect.

Higher WL similarity indicates greater structural similarity: 1.0 for
identical (isomorphic, up to the WL coloring) graphs, 0.0 for maximally
dissimilar ones.
"""

import csv
from pathlib import Path

from grakel import WeisfeilerLehman, VertexHistogram, graph_from_networkx

from topology_report import _undirected_projection, load_graph_tsv


def _labeled_undirected_projection(graph):
    """
    Build the simple undirected projection of a `MultiDiGraph`, labeled for
    the WL kernel.

    The WL kernel needs an initial per-node label to seed its neighborhood
    hashing. Node identity can't be used here -- entity IDs don't correspond
    between a real graph and a synthetic one (PyGraft names synthetic
    entities generically, `E1`, `E2`, ..., see `README.md`), the same reason
    `calculate_spectral_distance` in `topology_report.py` never attempts
    entity alignment. Node **degree** in the simple projection is used as
    the label instead: this is standard practice for comparing structurally
    (rather than semantically) labeled graphs, and keeps the kernel
    comparing "does this graph have a similarly-shaped mix of hub/leaf
    neighborhoods" rather than anything tied to specific node names.

    Args:
        graph: A `networkx.MultiDiGraph`, as returned by `load_graph_tsv`.

    Returns:
        A simple `networkx.Graph` with a `"label"` attribute on every node,
        set to that node's degree in the returned graph.
    """
    U, _ = _undirected_projection(graph)
    for node in U.nodes():
        U.nodes[node]["label"] = U.degree(node)
    return U


def weisfeiler_lehman_similarity(graph_real, graph_synthetic, h=3):
    """
    Compute the normalized WL subtree kernel similarity between two graphs.

    Args:
        graph_real: The target graph, as a `networkx.MultiDiGraph` (e.g.
            from `load_graph_tsv`).
        graph_synthetic: The graph being compared against the target, same
            type.
        h: Number of WL refinement iterations (neighborhood hops). Higher
            values capture larger-radius structural patterns at the cost of
            more computation; 2-3 is a reasonable range for graphs this
            repo's datasets are sized at.

    Returns:
        The normalized kernel similarity (float), where 1.0 means identical
        structure (up to the degree-based WL coloring) and 0.0 means
        maximally dissimilar.
    """
    U_real = _labeled_undirected_projection(graph_real)
    U_synth = _labeled_undirected_projection(graph_synthetic)

    grakel_graphs = list(
        graph_from_networkx([U_real, U_synth], node_labels_tag="label")
    )
    kernel = WeisfeilerLehman(n_iter=h, base_graph_kernel=VertexHistogram, normalize=True)
    similarity_matrix = kernel.fit_transform(grakel_graphs)
    return float(similarity_matrix[0, 1])


def kernel_report(
    real_file, synthetic_file, output_csv, exclude_predicates=None, h_values=(1, 2, 3)
):
    """
    Compute WL-kernel similarity at several `h` values and export the
    results to a CSV file (metric, value columns).

    Args:
        real_file: Path to the "real" graph's TSV edge-list file.
        synthetic_file: Path to the "synthetic" graph's TSV edge-list file.
        output_csv: Path to write the CSV report to. Parent directories are
            created as needed; an existing file at this path is overwritten.
        exclude_predicates: Optional iterable of predicate/relation labels
            to leave out of the graphs before comparing (see
            `load_graph_tsv`).
        h_values: WL iteration counts to report similarity at.
    """
    real_graph = load_graph_tsv(real_file, exclude_predicates=exclude_predicates)
    synthetic_graph = load_graph_tsv(synthetic_file, exclude_predicates=exclude_predicates)

    rows = [
        (f"wl_similarity_h{h}", weisfeiler_lehman_similarity(real_graph, synthetic_graph, h=h))
        for h in h_values
    ]

    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        writer.writerows(rows)


if __name__ == "__main__":
    # Replace these paths with your own files
    real_file = ".data/french_royalty/normalized/french_royalty.tsv"
    synthetic_file = ".data/french_royalty/pygraft/french_royalty.tsv"
    output_csv = "output/french_royalty/kernel_report.csv"

    # Predicates to leave out of every measurement below
    exclude_predicates = {"type"}

    kernel_report(
        real_file=real_file,
        synthetic_file=synthetic_file,
        output_csv=output_csv,
        exclude_predicates=exclude_predicates,
    )
