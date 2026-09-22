"""
Export a graph as GraphML with PageRank precomputed, for visual inspection
in Cytoscape (map node size/color to the `pagerank` attribute).
"""

from pathlib import Path

import networkx as nx

from topology_report import calculate_pagerank, load_graph_tsv


def export_graphml(tsv_file, output_path, exclude_predicates=None):
    """
    Load a TSV edge-list graph, attach each node's PageRank score as a
    `pagerank` attribute, and write it out as GraphML.

    PageRank is computed the same way `topology_report.py`'s
    `calculate_pagerank` does (collapsed to a simple `DiGraph`, weighted by
    relation multiplicity), so the exported value matches what the topology
    report itself measures.

    Args:
        tsv_file: Path to the graph's TSV edge-list file.
        output_path: Path to write the `.graphml` file to. Parent
            directories are created as needed; an existing file at this
            path is overwritten.
        exclude_predicates: Optional iterable of predicate/relation labels
            to leave out of the graph (see `load_graph_tsv`).
    """
    graph = load_graph_tsv(tsv_file, exclude_predicates=exclude_predicates)
    pagerank_scores = calculate_pagerank(graph)
    for node, score in zip(graph.nodes(), pagerank_scores):
        graph.nodes[node]["pagerank"] = float(score)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    nx.write_graphml(graph, output_path)


if __name__ == "__main__":
    # Replace these paths with your own files
    export_graphml(
        tsv_file=".data/french_royalty/normalized/french_royalty.tsv",
        output_path="output/french_royalty/normalized.graphml",
        exclude_predicates={"type"},
    )
    export_graphml(
        tsv_file=".data/french_royalty/skgg/french_royalty.tsv",
        output_path="output/french_royalty/skgg.graphml",
        exclude_predicates={"type"},
    )
