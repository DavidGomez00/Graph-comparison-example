"""
Topological similarity between two graphs.

Compares a "real" graph against a "synthetic" one along three complementary
axes:

1. Spectral distance: Euclidean distance between the sorted eigenvalues of
   the normalized Laplacian matrix of each graph. It is sensitive to global
   structural properties (connectivity, community structure, overall shape)
   rather than to individual node degrees.
2. Jensen-Shannon divergence (degrees): compares the in-degree and
   out-degree distributions of the two graphs node by node. It captures how
   similar the local connectivity patterns are, independent of global
   structure.
3. Jensen-Shannon divergence (predicates): compares how the two graphs'
   subject-object pairs are distributed across predicates/relation types.
   Unlike node degrees, predicate labels are shared vocabulary between the
   two graphs (the synthetic graph is generated from the real graph's
   schema), so this one captures whether each relation type is exercised
   proportionally as often in both, not just whether degree shapes match.
4. Structural metrics: undirected-projection edge count, node/edge
   triangles, clustering coefficient, and max/std in- and out-degree.
   These describe local closure structure (how much a graph's neighborhoods
   close into triangles) and degree-skew (how hub-like the graph is),
   neither of which the spectral or JS-divergence axes above capture on
   their own.
5. PageRank and local-clustering-coefficient distributions: compared via
   both Jensen-Shannon divergence and Wasserstein (earth mover's) distance.
   PageRank captures whether the two graphs create comparably realistic hub
   nodes (a node's degree alone doesn't say how *important* its neighbors
   consider it); local clustering coefficient captures the same closure
   structure as the global `clustering_coefficient` above, but as a full
   per-node distribution rather than a single averaged scalar, so two graphs
   with the same global transitivity but very differently-shaped
   neighborhoods are told apart.

Lower values indicate greater similarity for all JS-divergence,
Wasserstein-distance, and spectral-distance metrics; the structural metrics
are reported side by side (real vs. synthetic) rather than as a single
similarity score.
"""

import csv
import re
from collections import Counter
from pathlib import Path

import networkx as nx
import numpy as np
from scipy.linalg import eigvalsh
from scipy.spatial.distance import jensenshannon
from scipy.stats import wasserstein_distance

# Matches the position just before an internal capital letter, e.g. the "T"
# in "assignedTo" -- used to canonicalize predicate names (see
# `_normalize_predicate`).
_CAMEL_HUMP_RE = re.compile(r"(?<!^)(?=[A-Z])")


def _iter_triples(file_path):
    """
    Yield (source, predicate, target) tuples from a TSV edge-list file.

    The file is assumed to have three tab-separated columns per line:
    Source, Interaction, Target. This is the shared parsing/validation
    helper behind both `load_graph_tsv` (topology only, predicate dropped)
    and `count_predicate_pairs` (predicate-aware).

    IMPORTANT: this is deliberately NOT implemented as
    `nx.read_edgelist(file_path, delimiter="\\t", data=False)`. That call
    would take the *first two* tab-separated tokens of each line as the
    edge endpoints (Source, Interaction) silently dropping the
    Target column and producing a completely wrong graph (edges pointing
    at relation-label strings instead of at target entities). Columns 0
    and 2 are therefore selected explicitly here.

    Args:
        file_path: Path to the TSV edge-list file.

    Yields:
        (source, predicate, target) string tuples, one per non-empty line.
    """
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
            yield columns[0], columns[1], columns[2]


def load_graph_tsv(file_path, exclude_predicates=None):
    """
    Load a directed graph from a TSV edge list.

    Only the Source and Target columns are used to build edges; the
    Interaction column (the relation label) is ignored (beyond the
    `exclude_predicates` filter below), since this is the pure-topology view
    of the graph (see `count_predicate_pairs` for the predicate-aware view).

    IMPORTANT: the returned graph is a `MultiDiGraph`, not a plain
    `DiGraph`, and that is load-bearing. Because the Interaction column is
    dropped, two triples that share the same Source and Target but differ
    only in relation (e.g. `Bob reportsTo Alice` and `Bob knows Alice`)
    become the same `(source, target)` pair. A plain `DiGraph` treats
    `add_edge(u, v)` as idempotent and silently collapses such duplicate
    pairs into a single edge, undercounting the in/out-degree of every
    node involved -- with no warning, since this is valid `DiGraph` usage.
    `office.tsv` has two such pairs (`Bob`-`Alice`, `Charlie`-`Bob`), which
    previously made `calculate_js_divergence` report a non-zero divergence
    against a synthetic graph whose per-node degree distribution (as
    recorded in `office_nodes.csv`/`office_pygraft_nodes.csv`, exported
    from a multigraph-aware source) was actually identical: the "real"
    side had quietly lost edges that the synthetic side hadn't.
    `MultiDiGraph` keeps each triple as its own parallel edge, so
    `in_degree()`/`out_degree()` match the true edge count regardless of
    how many relations connect the same pair of nodes.

    Note: a node only enters the resulting graph if it appears in at least
    one edge line. Because of this, fully isolated nodes (0 in-degree AND
    0 out-degree) can never exist in a graph built this way. Nodes with
    in-degree 0 or out-degree 0 can and do occur, though, and are counted
    separately in `__main__`.

    Args:
        file_path: Path to the TSV edge-list file.
        exclude_predicates: Optional iterable of predicate/relation labels
            to leave out of the graph entirely (e.g. `{"type"}` to drop
            rdf:type-like class-membership edges and restrict the graph to
            entity-to-entity relationships). Matched via
            `_normalize_predicate`, so it's insensitive to the camelCase vs.
            snake_case differences between the real and synthetic graphs'
            predicate spellings. A node that only ever appears in excluded
            edges is dropped from the resulting graph entirely, same as any
            other node absent from every edge line (see the "Note" above).

    Returns:
        A `networkx.MultiDiGraph` built from the file's Source/Target
        columns, with one parallel edge per (non-excluded) triple (so
        same-direction triples between the same pair of nodes are preserved
        rather than collapsed).
    """
    exclude = {_normalize_predicate(p) for p in (exclude_predicates or ())}
    graph = nx.MultiDiGraph()
    for source, predicate, target in _iter_triples(file_path):
        if _normalize_predicate(predicate) in exclude:
            continue
        graph.add_edge(source, target)
    return graph


def _normalize_predicate(predicate):
    """
    Canonicalize a predicate/relation label for cross-graph comparison.

    Different graph variants spell the same relation differently in two
    independent ways this collapses:

    1. **Naming convention**: a real-world graph and a pygraft-synthesized
       one can use different conventions for what is semantically the same
       relation -- e.g. the office ontology's camelCase
       `assignedTo`/`reportsTo` vs. pygraft's snake_case
       `assigned_to`/`reports_to`.
    2. **Full URI vs. bare local name**: some variants spell a predicate as
       a full URI (e.g. `http://FrenchRoyalty.org/child`, or
       `http://www.w3.org/2000/01/rdf-schema#type`) while others use just
       the local name (`child`, `type`). This repo's own french_royalty
       variants mix both -- `pygraft`/`source` use bare names, `normalized`/
       `skgg` use full URIs -- so without stripping the namespace first,
       `_normalize_predicate` would treat every predicate as unique to its
       side, silently maximizing every predicate-based JS-divergence *and*
       breaking `exclude_predicates` matching (e.g. `exclude_predicates=
       {"type"}` would fail to exclude a `rdf-schema#type` URI, leaking
       type-membership edges into one side's graph but not the other's).

    Comparing raw predicate strings would treat any of the above as unrelated
    categories and understate how similar the predicate-pair distributions
    actually are. The local name is taken first (text after the last `/` or
    `#`, or the whole string if neither appears), then an underscore is
    inserted before each internal capital letter and the result is
    lowercased, collapsing every spelling to the same key (`assignedTo` ->
    `assigned_to`, `http://.../assigned_to` -> `assigned_to`, unchanged).

    Args:
        predicate: A raw predicate/relation label, bare or a full URI.

    Returns:
        The lowercase, snake_case, namespace-stripped form of `predicate`.
    """
    local_name = re.split(r"[/#]", predicate)[-1]
    return _CAMEL_HUMP_RE.sub("_", local_name).lower()


def count_predicate_pairs(file_path, exclude_predicates=None):
    """
    Count subject-object pairs per predicate in a TSV edge-list file.

    Each line contributes one pair to its predicate's count. Predicate
    labels are canonicalized with `_normalize_predicate` first, so that
    naming-convention differences between a real graph and a
    pygraft-synthesized one don't fragment what is really the same relation
    into separate categories.

    Args:
        file_path: Path to the TSV edge-list file.
        exclude_predicates: Optional iterable of predicate/relation labels
            to omit from the counts entirely (see `load_graph_tsv` for
            matching semantics -- the same `_normalize_predicate` matching
            is used here).

    Returns:
        A `collections.Counter` mapping normalized predicate -> pair count,
        excluding any predicate named in `exclude_predicates`.
    """
    exclude = {_normalize_predicate(p) for p in (exclude_predicates or ())}
    counts = Counter()
    for _source, predicate, _target in _iter_triples(file_path):
        normalized = _normalize_predicate(predicate)
        if normalized in exclude:
            continue
        counts[normalized] += 1
    return counts


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


def calculate_predicate_js_divergence(counts_real, counts_synthetic):
    """
    Compute the JS divergence between two per-predicate pair-count
    distributions.

    Unlike `calculate_js_divergence` (which compares in-/out-degree
    sequences as unordered multisets, since node identities don't
    correspond across a real graph and a synthetic one with renamed
    entities), predicate labels here ARE shared vocabulary between the two
    graphs -- the synthetic graph is generated from the real graph's
    schema. So the two count vectors must be aligned *by predicate name*
    rather than by sorting: sorting would silently compare unrelated
    predicates against each other whenever their pair counts happen to
    coincide in rank (e.g. `office.tsv`'s `[5, 4, 2, 2, 2]` against
    `office_pygraft.tsv`'s `[5, 3, 3, 3, 1]`, sorted, would line up `knows`
    against whichever predicate happens to also be the second-most common
    in the other graph -- not necessarily `knows` there).

    A predicate present in only one graph is treated as having a count of 0
    in the other, rather than being dropped, so a predicate the synthetic
    graph invented (or omitted) still counts against similarity.

    Args:
        counts_real: predicate -> pair count for the real graph, e.g. from
            `count_predicate_pairs`.
        counts_synthetic: predicate -> pair count for the synthetic graph.

    Returns:
        The Jensen-Shannon divergence (float, base 2), where 0 means the
        two graphs distribute their subject-object pairs across predicates
        in exactly the same proportions.
    """
    predicates = sorted(set(counts_real) | set(counts_synthetic))
    counts_vec_real = np.array([counts_real.get(p, 0) for p in predicates], dtype=float)
    counts_vec_synth = np.array(
        [counts_synthetic.get(p, 0) for p in predicates], dtype=float
    )

    pdf_real = counts_vec_real / counts_vec_real.sum()
    pdf_synth = counts_vec_synth / counts_vec_synth.sum()

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

    If a graph is a `MultiDiGraph` (as `load_graph_tsv` returns), its
    undirected version is a `MultiGraph`, and networkx builds the Laplacian
    from edge-weight sums -- so a node pair connected by several parallel
    edges (multiple relations between the same two entities) contributes
    more weight than a pair connected by one, which is the intended,
    structure-preserving behavior rather than an artifact.

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


def _undirected_projection(graph):
    """
    Derive both undirected views of a `MultiDiGraph` that the structural,
    clustering, and triangle metrics share.

    Args:
        graph: A `networkx.MultiDiGraph`, as returned by `load_graph_tsv`.

    Returns:
        A `(U, U_multi)` tuple: `U_multi` is `graph.to_undirected()` (a
        `MultiGraph`, direction dropped but parallel edges preserved, so
        `U_multi.number_of_edges(u, v)` gives the true relation count
        between `u` and `v`); `U` is the simple projection
        (`nx.Graph(U_multi)`, parallel edges collapsed to one).
    """
    U_multi = graph.to_undirected()
    U = nx.Graph(U_multi)
    return U, U_multi


def _weighted_edge_triangles(U, U_multi):
    """
    Count triangles in `U`, weighted by each side's edge multiplicity in
    `U_multi`.

    For every triad `{u, v, w}` that forms a triangle in `U`, the
    contribution is `mult(u, v) * mult(v, w) * mult(u, w)` (the multiplicity
    being the number of parallel edges -- i.e. relations -- connecting that
    pair in `U_multi`), summed over all triangles.

    This is deliberately NOT implemented as `itertools.combinations(U.nodes(),
    3)` filtered by `has_edge` three times over, which is the direct
    translation of the triangle definition but costs O(n^3) -- intractable
    for graphs with thousands of nodes (this repo's own datasets, e.g.
    french_royalty, are in that range). Instead this uses the standard
    "forward" triangle-listing algorithm (Schank & Wagner): nodes are
    ordered (here by degree, ties broken by node id, for a stable order),
    each node keeps only the neighbors that come after it in that order, and
    triangles are found by intersecting those "forward" neighbor sets.
    Every triangle is discovered exactly once this way, in O(m^1.5) instead
    of O(n^3).

    Args:
        U: A simple (no parallel edges) `networkx.Graph` -- the undirected
            projection to find triangles in.
        U_multi: The corresponding `networkx.MultiGraph` (same nodes/edges as
            `U`, but with parallel edges preserved) to read multiplicities
            from via `number_of_edges(u, v)`.

    Returns:
        The multiplicity-weighted triangle count (int).
    """
    order = {n: i for i, n in enumerate(sorted(U.nodes(), key=lambda n: (U.degree(n), n)))}
    forward_neighbors = {n: {w for w in U[n] if order[w] > order[n]} for n in U.nodes()}

    total = 0
    for u, u_forward in forward_neighbors.items():
        for v in u_forward:
            for w in u_forward & forward_neighbors[v]:
                total += (
                    U_multi.number_of_edges(u, v)
                    * U_multi.number_of_edges(v, w)
                    * U_multi.number_of_edges(u, w)
                )
    return total


def calculate_structural_metrics(graph):
    """
    Compute local closure and degree-skew metrics for a single graph.

    Args:
        graph: A `networkx.MultiDiGraph`, as returned by `load_graph_tsv`.

    Returns:
        A dict with the following keys:
        - `undirected_edges`: number of edges in the simple (parallel edges
          collapsed) undirected projection of `graph`. Distinct from
          `graph.number_of_edges()` (the directed, multi-edge triple count
          reported elsewhere as `real_edges`/`synthetic_edges`).
        - `node_triangles`: standard triangle count on the undirected
          projection -- each closed 3-node triad counted once, regardless of
          how many relations/directions link its sides.
        - `edge_triangles`: multiplicity-weighted triangle count (see
          `_weighted_edge_triangles`); `>= node_triangles`, equal only when
          no triangle side has more than one connecting edge.
        - `clustering_coefficient`: global transitivity of the undirected
          projection (`3 * node_triangles / wedges`).
        - `max_in_degree`, `max_out_degree`, `std_in_degree`,
          `std_out_degree`: summary stats of `graph`'s in-/out-degree
          sequences.
    """
    in_degrees = np.array([d for _, d in graph.in_degree()])
    out_degrees = np.array([d for _, d in graph.out_degree()])

    U, U_multi = _undirected_projection(graph)

    node_triangles = sum(nx.triangles(U).values()) // 3

    return {
        "undirected_edges": U.number_of_edges(),
        "node_triangles": node_triangles,
        "edge_triangles": _weighted_edge_triangles(U, U_multi),
        "clustering_coefficient": nx.transitivity(U),
        "max_in_degree": int(in_degrees.max()) if in_degrees.size else 0,
        "max_out_degree": int(out_degrees.max()) if out_degrees.size else 0,
        "std_in_degree": float(in_degrees.std()) if in_degrees.size else 0.0,
        "std_out_degree": float(out_degrees.std()) if out_degrees.size else 0.0,
    }


def calculate_pagerank(graph):
    """
    Compute PageRank scores for every node in a graph.

    `graph` is collapsed from a `MultiDiGraph` to a simple `DiGraph` first,
    with each retained edge weighted by its original multiplicity (how many
    parallel relations connected that ordered pair) -- the same "parallel
    edges = a stronger link" treatment `calculate_spectral_distance` already
    gives multi-edges via the (weighted) Laplacian, kept consistent here so
    a node linked to a neighbor by several relations is treated as more
    strongly connected to it than one linked by a single relation.

    Args:
        graph: A `networkx.MultiDiGraph`, as returned by `load_graph_tsv`.

    Returns:
        A `numpy.ndarray` of PageRank scores, one per node (order matches
        `graph.nodes()`).
    """
    D = nx.DiGraph()
    D.add_nodes_from(graph.nodes())
    for u, v in graph.edges():
        if D.has_edge(u, v):
            D[u][v]["weight"] += 1
        else:
            D.add_edge(u, v, weight=1)
    scores = nx.pagerank(D, weight="weight")
    return np.array([scores[n] for n in graph.nodes()])


def calculate_local_clustering(graph):
    """
    Compute the local clustering coefficient of every node in a graph.

    Unlike `calculate_structural_metrics`'s `clustering_coefficient` (global
    transitivity, `3 * triangles / wedges`, a single scalar for the whole
    graph), this returns the full per-node distribution, so two graphs that
    happen to share the same global transitivity but arrange their triangles
    into very differently-shaped neighborhoods (e.g. concentrated in a few
    dense clusters vs. spread evenly) can still be told apart.

    Args:
        graph: A `networkx.MultiDiGraph`, as returned by `load_graph_tsv`.

    Returns:
        A `numpy.ndarray` of local clustering coefficients, one per node.
    """
    U, _ = _undirected_projection(graph)
    coefficients = nx.clustering(U)
    return np.array([coefficients[n] for n in graph.nodes()])


def calculate_distribution_divergence(values_real, values_synthetic, bins=30):
    """
    Compare two continuous-valued distributions via both Jensen-Shannon
    divergence and Wasserstein distance.

    This generalizes `calculate_js_divergence` (which bins on integer degree
    values, one bin per degree, exact) to distributions like PageRank scores
    or local clustering coefficients, which are continuous floats in
    [0, 1] rather than small integers -- `bins` histogram bins spanning the
    combined range of both samples are used for the JS-divergence half.
    Wasserstein distance is computed directly from the raw samples (no
    binning), via `scipy.stats.wasserstein_distance`, which is standard for
    comparing degree-like distributions in the graph-generation literature
    and, unlike a binned JS-divergence, is sensitive to *how far apart*
    mismatched values are rather than only whether they fall in the same
    bin.

    Args:
        values_real: 1D array-like of samples from the target graph.
        values_synthetic: 1D array-like of samples from the graph being
            compared against the target.
        bins: Number of histogram bins to use for the JS-divergence half.

    Returns:
        A dict with keys `js_divergence` (float, base 2, bounded [0, 1]) and
        `wasserstein_distance` (float, 0 means identical distributions,
        unbounded above).
    """
    values_real = np.asarray(values_real, dtype=float)
    values_synthetic = np.asarray(values_synthetic, dtype=float)

    combined_min = min(values_real.min(), values_synthetic.min())
    combined_max = max(values_real.max(), values_synthetic.max())
    bin_edges = np.linspace(combined_min, combined_max, bins + 1)

    pdf_real, _ = np.histogram(values_real, bins=bin_edges, density=True)
    pdf_synth, _ = np.histogram(values_synthetic, bins=bin_edges, density=True)

    js_distance = jensenshannon(pdf_real, pdf_synth, base=2)
    js_divergence = js_distance**2

    return {
        "js_divergence": js_divergence,
        "wasserstein_distance": wasserstein_distance(values_real, values_synthetic),
    }


def topology_report(real_file, synthetic_file, output_csv, exclude_predicates=None):
    """
    Compute the full topology comparison between two graphs and export the
    results to a CSV file (metric, value columns) instead of printing them.

    Args:
        real_file: Path to the "real" graph's TSV edge-list file.
        synthetic_file: Path to the "synthetic" graph's TSV edge-list file.
        output_csv: Path to write the CSV report to. Parent directories are
            created as needed; an existing file at this path is overwritten.
        exclude_predicates: Optional iterable of predicate/relation labels
            to leave out of every measurement (see `load_graph_tsv`).
    """
    real_graph = load_graph_tsv(real_file, exclude_predicates=exclude_predicates)
    synthetic_graph = load_graph_tsv(
        synthetic_file, exclude_predicates=exclude_predicates
    )

    # Diagnostic only: count nodes that are pure sources (in-degree 0) or
    # pure sinks (out-degree 0) in each graph.
    zero_in_real = sum(1 for _, d in real_graph.in_degree() if d == 0)
    zero_out_real = sum(1 for _, d in real_graph.out_degree() if d == 0)
    zero_in_synth = sum(1 for _, d in synthetic_graph.in_degree() if d == 0)
    zero_out_synth = sum(1 for _, d in synthetic_graph.out_degree() if d == 0)

    # 1. Jensen-Shannon divergence (values closer to 0 = greater similarity)
    js_in = calculate_js_divergence(real_graph, synthetic_graph, "in")
    js_out = calculate_js_divergence(real_graph, synthetic_graph, "out")

    # 1.5. Jensen-Shannon divergence for the pairs-per-predicate distribution
    predicate_counts_real = count_predicate_pairs(
        real_file, exclude_predicates=exclude_predicates
    )
    predicate_counts_synth = count_predicate_pairs(
        synthetic_file, exclude_predicates=exclude_predicates
    )
    js_predicates = calculate_predicate_js_divergence(
        predicate_counts_real, predicate_counts_synth
    )

    # 2. Spectral distance (values closer to 0 = greater global structural similarity)
    spectral_distance = calculate_spectral_distance(
        real_graph, synthetic_graph, normalized=False
    )
    normalized_spectral_dist = calculate_spectral_distance(
        real_graph, synthetic_graph, normalized=True
    )

    # 3. Structural metrics (local closure / degree-skew, reported side by
    # side rather than as a single similarity score)
    structural_real = calculate_structural_metrics(real_graph)
    structural_synth = calculate_structural_metrics(synthetic_graph)

    # 4. PageRank and local-clustering-coefficient distributions (both
    # JS-divergence and Wasserstein distance)
    pagerank_real = calculate_pagerank(real_graph)
    pagerank_synth = calculate_pagerank(synthetic_graph)
    pagerank_divergence = calculate_distribution_divergence(pagerank_real, pagerank_synth)

    local_clustering_real = calculate_local_clustering(real_graph)
    local_clustering_synth = calculate_local_clustering(synthetic_graph)
    local_clustering_divergence = calculate_distribution_divergence(
        local_clustering_real, local_clustering_synth
    )
    real_average_clustering = float(local_clustering_real.mean())
    synthetic_average_clustering = float(local_clustering_synth.mean())

    rows = [
        ("real_nodes", real_graph.number_of_nodes()),
        ("real_edges", real_graph.number_of_edges()),
        ("real_zero_in_degree_nodes", zero_in_real),
        ("real_zero_out_degree_nodes", zero_out_real),
        ("real_undirected_edges", structural_real["undirected_edges"]),
        ("real_node_triangles", structural_real["node_triangles"]),
        ("real_edge_triangles", structural_real["edge_triangles"]),
        ("real_clustering_coefficient", structural_real["clustering_coefficient"]),
        ("real_max_in_degree", structural_real["max_in_degree"]),
        ("real_max_out_degree", structural_real["max_out_degree"]),
        ("real_std_in_degree", structural_real["std_in_degree"]),
        ("real_std_out_degree", structural_real["std_out_degree"]),
        ("real_average_clustering", real_average_clustering),
        ("synthetic_nodes", synthetic_graph.number_of_nodes()),
        ("synthetic_edges", synthetic_graph.number_of_edges()),
        ("synthetic_zero_in_degree_nodes", zero_in_synth),
        ("synthetic_zero_out_degree_nodes", zero_out_synth),
        ("synthetic_undirected_edges", structural_synth["undirected_edges"]),
        ("synthetic_node_triangles", structural_synth["node_triangles"]),
        ("synthetic_edge_triangles", structural_synth["edge_triangles"]),
        ("synthetic_clustering_coefficient", structural_synth["clustering_coefficient"]),
        ("synthetic_max_in_degree", structural_synth["max_in_degree"]),
        ("synthetic_max_out_degree", structural_synth["max_out_degree"]),
        ("synthetic_std_in_degree", structural_synth["std_in_degree"]),
        ("synthetic_std_out_degree", structural_synth["std_out_degree"]),
        ("synthetic_average_clustering", synthetic_average_clustering),
        ("js_divergence_in_degree", js_in),
        ("js_divergence_out_degree", js_out),
        ("js_divergence_pairs_per_predicate", js_predicates),
        ("js_divergence_pagerank", pagerank_divergence["js_divergence"]),
        ("wasserstein_pagerank", pagerank_divergence["wasserstein_distance"]),
        ("js_divergence_local_clustering", local_clustering_divergence["js_divergence"]),
        ("wasserstein_local_clustering", local_clustering_divergence["wasserstein_distance"]),
        ("spectral_distance", spectral_distance),
        ("normalized_spectral_distance", normalized_spectral_dist),
    ]

    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        writer.writerows(rows)


if __name__ == "__main__":
    # Replace these paths with your own files
    real_file = "data/french_royalty/source/french_royalty.tsv"
    synthetic_file = "data/french_royalty/pygraft/french_royalty.tsv"
    output_csv = "output/french_royalty/topology_report.csv"

    # Predicates to leave out of every measurement below
    exclude_predicates = {"type"}

    topology_report(
        real_file=real_file,
        synthetic_file=synthetic_file,
        output_csv=output_csv,
        exclude_predicates=exclude_predicates,
    )
