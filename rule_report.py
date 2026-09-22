"""
Global/logical comparison between two graphs' mined AMIE rule sets.

Complements `topology_report.py` (structural/statistical similarity) and
`kernel_report.py` (neighborhood-pattern similarity) with a comparison of
the *relational logic* each graph encodes: Horn rules such as
`?a servantOf ?b => ?a allyOf ?b`, mined separately from each graph via
AMIE3 (see `run_amie.py`). Since both graphs share the same relation names
(the synthetic graph is generated from the target's schema), mined rule
*patterns* are directly comparable between the two graphs without any
entity alignment.

This script does not run AMIE itself -- it takes the paths to two rule CSVs
already produced by `run_amie.py` (same column layout on both sides) and
reports which rule patterns are shared, which are unique to each side, and
how their support/confidence compare where a pattern appears in both.
"""

import csv
from pathlib import Path

import numpy as np
import pandas as pd


def canonical_rule(rule_str):
    """
    Rename an AMIE rule's variables (`?a`, `?b`, ...) by order of first
    appearance, so the same relational pattern mined from different graphs
    compares equal regardless of AMIE's internal variable naming.

    Args:
        rule_str: A rule's `rule` column value, e.g.
            `"?a  servantOf  ?b   => ?a  allyOf  ?b"`.

    Returns:
        The same rule text with every variable replaced by `?v0`, `?v1`, ...
        in order of first appearance.
    """
    mapping = {}
    tokens = []
    for tok in rule_str.split():
        if tok.startswith("?"):
            tok = mapping.setdefault(tok, f"?v{len(mapping)}")
        tokens.append(tok)
    return " ".join(tokens)


def rule_predicates(rule_str):
    """
    The set of relation/predicate names used anywhere in an AMIE rule (body
    and head), e.g. `{"enemyOf", "type"}` for
    `"?a enemyOf ?f ?f type ?b => ?a type ?b"`.

    Args:
        rule_str: A rule's `rule` column value.

    Returns:
        A set of predicate name strings.
    """
    return {tok for tok in rule_str.replace("=>", " ").split() if not tok.startswith("?")}


def load_rules(path, exclude_predicates=None):
    """
    Load an AMIE rules CSV (see `run_amie.py`) indexed by canonical
    pattern, alongside its original columns.

    Args:
        path: Path to a rules CSV produced by `run_amie.py`.
        exclude_predicates: Optional iterable of predicate/relation names
            (e.g. `{"type"}`) -- any mined rule using one of these
            predicates, anywhere in its body or head, is dropped.

    Returns:
        A `pandas.DataFrame` indexed by `canonical_rule`, with the original
        columns plus `canonical_rule` preserved as a regular column too.
    """
    df = pd.read_csv(path)
    if exclude_predicates:
        exclude_predicates = set(exclude_predicates)
        df = df[~df["rule"].map(lambda r: bool(rule_predicates(r) & exclude_predicates))]
    df = df.copy()
    df["canonical_rule"] = df["rule"].map(canonical_rule)
    return df.set_index("canonical_rule")


def compare_rules(
    target_path,
    synthetic_path,
    target_label=None,
    synthetic_label=None,
    exclude_predicates=None,
):
    """
    Compare AMIE-mined rules from a target graph and a synthetic one.

    Args:
        target_path: Path to the target graph's AMIE rules CSV
            (`run_amie.py` output).
        synthetic_path: Path to the synthetic graph's AMIE rules CSV.
        target_label: Column label for the target's metrics; defaults to
            the target file's name.
        synthetic_label: Column label for the synthetic graph's metrics;
            defaults to the synthetic file's name.
        exclude_predicates: Optional iterable of predicate names to drop
            rules for (forwarded to `load_rules`), e.g. `{"type"}`.

    Returns:
        A `(summary, rules)` tuple:
        - `summary`: a `pandas.Series` with `num_rules_target`,
          `num_rules_synthetic`, `num_shared`, `num_target_only`,
          `num_synthetic_only`, and `jaccard_similarity`.
        - `rules`: a `pandas.DataFrame`, one row per distinct canonical
          pattern found in either graph, with `in_target`/`in_synthetic`
          flags and each side's `head_coverage`/`std_confidence`/
          `pca_confidence`/`positive_examples` side by side (`NaN` on the
          side that doesn't have that pattern).
    """
    target_label = target_label or f"Target ({Path(target_path).name})"
    synthetic_label = synthetic_label or f"Synthetic ({Path(synthetic_path).name})"

    t = load_rules(target_path, exclude_predicates=exclude_predicates)
    s = load_rules(synthetic_path, exclude_predicates=exclude_predicates)
    t_ids, s_ids = set(t.index), set(s.index)

    metric_cols = ["head_coverage", "std_confidence", "pca_confidence", "positive_examples"]
    rules = pd.DataFrame(index=sorted(t_ids | s_ids))
    rules.index.name = "canonical_rule"
    rules["rule"] = [t["rule"][i] if i in t_ids else s["rule"][i] for i in rules.index]
    rules["in_target"] = rules.index.isin(t_ids)
    rules["in_synthetic"] = rules.index.isin(s_ids)
    for col in metric_cols:
        rules[f"{col} ({target_label})"] = [t.loc[i, col] if i in t_ids else np.nan for i in rules.index]
        rules[f"{col} ({synthetic_label})"] = [s.loc[i, col] if i in s_ids else np.nan for i in rules.index]
    rules = (
        rules.reset_index(drop=True)
        .set_index("rule")
        .sort_values(["in_target", "in_synthetic"], ascending=False)
    )

    summary = pd.Series(
        {
            "num_rules_target": len(t_ids),
            "num_rules_synthetic": len(s_ids),
            "num_shared": len(t_ids & s_ids),
            "num_target_only": len(t_ids - s_ids),
            "num_synthetic_only": len(s_ids - t_ids),
            "jaccard_similarity": round(len(t_ids & s_ids) / len(t_ids | s_ids), 3) if (t_ids | s_ids) else float("nan"),
        },
        name="value",
    )

    return summary, rules


def rule_report(
    target_rules_csv,
    synthetic_rules_csv,
    summary_csv,
    rules_csv,
    target_label=None,
    synthetic_label=None,
    exclude_predicates=None,
):
    """
    Compute the full rule-set comparison between two graphs' AMIE output and
    export the results to two CSV files (rather than returning DataFrames
    for notebook display).

    Args:
        target_rules_csv: Path to the target graph's AMIE rules CSV.
        synthetic_rules_csv: Path to the synthetic graph's AMIE rules CSV.
        summary_csv: Path to write the summary (metric, value columns) to.
        rules_csv: Path to write the full rule-by-rule comparison table to.
        target_label: See `compare_rules`.
        synthetic_label: See `compare_rules`.
        exclude_predicates: See `compare_rules`.
    """
    summary, rules = compare_rules(
        target_rules_csv,
        synthetic_rules_csv,
        target_label=target_label,
        synthetic_label=synthetic_label,
        exclude_predicates=exclude_predicates,
    )

    summary_path = Path(summary_csv)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        writer.writerows(summary.items())

    rules_path = Path(rules_csv)
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    rules.to_csv(rules_path)


if __name__ == "__main__":
    # Replace these paths with your own files (produced by run_amie.py)
    target_rules_csv = "output/french_royalty/normalized_rules.csv"
    synthetic_rules_csv = "output/french_royalty/pygraft_rules.csv"
    summary_csv = "output/french_royalty/rule_summary.csv"
    rules_csv = "output/french_royalty/rule_comparison.csv"

    # Predicates to leave out of every rule below
    exclude_predicates = {"type"}

    rule_report(
        target_rules_csv=target_rules_csv,
        synthetic_rules_csv=synthetic_rules_csv,
        summary_csv=summary_csv,
        rules_csv=rules_csv,
        exclude_predicates=exclude_predicates,
    )
