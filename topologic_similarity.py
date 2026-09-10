"""
Topological similarity between two graphs.

Compares a "real" graph against a "synthetic" one along two complementary
axes:

1. Spectral distance: Euclidean distance between the sorted eigenvalues of
   the normalized Laplacian matrix of each graph. It is sensitive to global
   structural properties (connectivity, community structure, overall shape)
   rather than to individual node degrees.
2. Jensen-Shannon divergence: compares the in-degree and out-degree
   distributions of the two graphs node by node. It captures how similar the
   local connectivity patterns are, independent of global structure.

Lower values indicate greater similarity for both metrics.
"""

import networkx as nx
import numpy as np
from scipy.linalg import eigvalsh
from scipy.spatial.distance import jensenshannon


def load_graph_tsv(file_path):
    """
    Load a directed graph from a TSV edge list.

    The file is assumed to have three tab-separated columns per line:
    Source, Interaction, Target. Only the Source and Target columns are
    used to build edges; the Interaction column (the relation label) is
    ignored, since this script only performs pure topology analysis.

    IMPORTANT: this is deliberately NOT implemented as
    `nx.read_edgelist(file_path, delimiter="\\t", data=False)`. That call
    would take the *first two* tab-separated tokens of each line as the
    edge endpoints (Source, Interaction) silently dropping the
    Target column and producing a completely wrong graph (edges pointing
    at relation-label strings instead of at target entities). Columns 0
    and 2 are therefore selected explicitly here.

    Note: a node only enters the resulting graph if it appears in at least
    one edge line. Because of this, fully isolated nodes (0 in-degree AND
    0 out-degree) can never exist in a graph built this way. Nodes with
    in-degree 0 or out-degree 0 can and do occur, though, and are counted
    separately in `__main__`.

    Args:
        file_path: Path to the TSV edge-list file.

    Returns:
        A `networkx.DiGraph` built from the file's Source/Target columns.
    """
    graph = nx.DiGraph()
    with open(file_path, encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.rstrip("\n")
            if not line:
                continue
            columns = line.split("\t")
            if len(columns) < 3:
                raise ValueError(
                    f"{file_path}:{line_number}: expected 3 tab-separated columns "
                    f"(Source, Interaction, Target), got {len(columns)}: {line!r}"
                )
            source, _interaction, target = columns[0], columns[1], columns[2]
            graph.add_edge(source, target)
    return graph


def calculate_js_divergence(G_real, G_synthetic, degree_type="in"):
    """
    Compute the Jensen-Shannon divergence between the degree distributions
    of two graphs.

    The chosen degree sequence (in-degree or out-degree) of each graph is
    turned into a probability mass function over degree values (a
    normalized histogram with one bin per integer degree, from 0 to the
    largest degree seen in either graph), and the JS divergence between the
    two distributions is returned.

    `scipy.spatial.distance.jensenshannon` returns the JS *distance*
    (the square root of the divergence); it is squared here to recover the
    divergence itself. `base=2` is passed explicitly so the result follows
    the classic Lin (1991) definition and is bounded in [0, 1] — the
    convention most commonly used in the network-comparison literature
    (scipy's default is natural log, which would instead bound the
    divergence by ln(2) ≈ 0.693).

    Caveat: if a graph has no edges at all in the requested direction, its
    degree sequence is empty and `np.histogram(..., density=True)` can
    produce NaNs (0/0), which would propagate through to the returned
    value. This is not expected to happen for non-trivial input graphs but
    is worth knowing if this function ever returns `nan`.

    Args:
        G_real: The target graph.
        G_synthetic: The graph being compared against the target.
        degree_type: Either "in" or anything else, treated as
            "out" (out-degree).

    Returns:
        The Jensen-Shannon divergence (float, base 2), where 0 means
        identical degree distributions and 1 means maximally different.
    """
    if degree_type == "in":
        degrees_real = [d for n, d in G_real.in_degree()]
        degrees_synth = [d for n, d in G_synthetic.in_degree()]
    else:
        degrees_real = [d for n, d in G_real.out_degree()]
        degrees_synth = [d for n, d in G_synthetic.out_degree()]

    # Find the maximum degree across both graphs to align the histograms
    max_degree = max(
        max(degrees_real) if degrees_real else 0,
        max(degrees_synth) if degrees_synth else 0,
    )

    # Build bins from 0 up to the maximum degree (inclusive)
    bins = np.arange(max_degree + 2)

    # Build probability density functions (PDFs)
    pdf_real, _ = np.histogram(degrees_real, bins=bins, density=True)
    pdf_synth, _ = np.histogram(degrees_synth, bins=bins, density=True)

    # scipy computes the JS *distance*; the divergence is its square.
    # base=2 keeps the result bounded in [0, 1], matching common usage.
    js_distance = jensenshannon(pdf_real, pdf_synth, base=2)
    js_divergence = js_distance**2

    return js_divergence


def calculate_spectral_distance(G_real, G_synthetic, normalized: bool = True):
    """
    Compute the spectral distance between two graphs using the normalized
    Laplacian matrix.

    Both graphs are converted to undirected graphs first, since the
    normalized Laplacian spectrum is defined for undirected graphs and is
    the standard basis for this kind of comparison. The eigenvalues of each
    normalized Laplacian are sorted, the shorter spectrum is zero-padded so
    both have the same length, and the Euclidean distance between the two
    resulting vectors is returned.

    Limitation: normalized-Laplacian eigenvalues lie in [0, 2], and a value
    of 0 corresponds to a disconnected component. Zero-padding the smaller
    graph's spectrum therefore implicitly treats every "missing" node as an
    extra disconnected component. This is a common, well-known
    simplification in the graph-comparison literature, but it means the
    resulting distance can be inflated by a large difference in node count
    alone, independent of real structural dissimilarity. When comparing
    graphs of very different sizes, consider alternatives such as
    comparing smoothed eigenvalue-density curves (e.g. NetLSD, Tsitsulin et
    al. 2018) or the Ipsen-Mikhailov distance instead of raw zero-padding.

    Args:
        G_real: The reference ("real") graph.
        G_synthetic: The graph being compared against the reference.

    Returns:
        The Euclidean distance between the two (zero-padded) sorted
        eigenvalue spectra (float), where 0 means identical spectra.
    """
    U_real = G_real.to_undirected()
    U_synth = G_synthetic.to_undirected()

    # Compute the normalized Laplacian matrix (dense, for scipy's eigvalsh)
    if normalized:
        L_real = nx.normalized_laplacian_matrix(U_real).todense()
        L_synth = nx.normalized_laplacian_matrix(U_synth).todense()
    else:
        L_real = nx.laplacian_matrix(U_real).todense()
        L_synth = nx.laplacian_matrix(U_synth).todense()

    # Get the eigenvalues (spectrum) and sort them
    spectrum_real = np.sort(eigvalsh(L_real))
    spectrum_synth = np.sort(eigvalsh(L_synth))

    # If the graphs have a different number of nodes, zero-pad the smaller
    # spectrum (a 0 eigenvalue in the normalized spectrum represents a
    # disconnected component — see the "Limitation" note in the docstring)
    n_max = max(len(spectrum_real), len(spectrum_synth))
    spectrum_real = np.pad(
        spectrum_real, (0, n_max - len(spectrum_real)), constant_values=0
    )
    spectrum_synth = np.pad(
        spectrum_synth, (0, n_max - len(spectrum_synth)), constant_values=0
    )

    # Euclidean distance between the two spectra
    distance = np.linalg.norm(spectrum_real - spectrum_synth)
    return distance


if __name__ == "__main__":
    # Replace these paths with your own files
    real_file = ".data/mario/simple_mario.tsv"
    synthetic_file = ".data/mario/simple_pygraft.tsv"

    print("Loading graphs...")
    real_graph = load_graph_tsv(real_file)
    synthetic_graph = load_graph_tsv(synthetic_file)

    # Diagnostic only: count nodes that are pure sources (in-degree 0) or
    # pure sinks (out-degree 0) in each graph.
    zero_in_real = sum(1 for _, d in real_graph.in_degree() if d == 0)
    zero_out_real = sum(1 for _, d in real_graph.out_degree() if d == 0)
    zero_in_synth = sum(1 for _, d in synthetic_graph.in_degree() if d == 0)
    zero_out_synth = sum(1 for _, d in synthetic_graph.out_degree() if d == 0)

    print(
        f"Real graph: {real_graph.number_of_nodes()} nodes, {real_graph.number_of_edges()} edges, {zero_in_real} nodes with in-degree=0, {zero_out_real} nodes with out-degree 0"
    )
    print(
        f"Synthetic graph: {synthetic_graph.number_of_nodes()} nodes, {synthetic_graph.number_of_edges()} edges, {zero_in_synth} nodes with in-degree=0, {zero_out_synth} nodes with out-degree 0"
    )
    print("-" * 50)

    # 1. Jensen-Shannon divergence (values closer to 0 = greater similarity)
    js_in = calculate_js_divergence(real_graph, synthetic_graph, "in")
    js_out = calculate_js_divergence(real_graph, synthetic_graph, "out")

    print(f"JS divergence (in-degree):  {js_in:.4f}")
    print(f"JS divergence (out-degree): {js_out:.4f}")

    # 2. Spectral distance (values closer to 0 = greater global structural similarity)
    spectral_distance = calculate_spectral_distance(
        real_graph, synthetic_graph, normalized=False
    )
    normalized_spectral_dist = calculate_spectral_distance(
        real_graph, synthetic_graph, normalized=True
    )

    print(f"Spectral distance:          {spectral_distance:.4f}")
    print(f"Norm. Spectral distance:    {normalized_spectral_dist:.4f}")
