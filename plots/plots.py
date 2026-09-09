import math
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import MaxNLocator

# Fixed categorical order (validated for colorblind-safety) -- reused across
# figures so a given slot always means the same thing when the same columns
# are plotted in the same order. Never cycle/reassign these per-call.
CATEGORICAL_PALETTE = [
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
]

CHART_SURFACE = "#fcfcfb"
PRIMARY_INK = "#0b0b0b"
# Was "#898781": legible on a laptop screen but a projector's low contrast
# ratio and bright lamp wash it out, taking axis labels/ticks/legend text
# (everything but the title, which uses PRIMARY_INK) down to near-invisible.
MUTED_INK = "#4a4944"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"


def plot_column_histograms(
    csv_path: str,
    columns: str | list[str],
    bins: int = 30,
    ncols: int = 1,
    figsize_per_plot: tuple[float, float] = (4, 3),
    save_path: str | Path | None = None,
):
    """Plot histograms for one or more CSV columns together in a single image.

    Each column gets its own small-multiple subplot (so differently-scaled
    columns don't distort each other), laid out in a grid within one figure.

    Args:
        - csv_path: path to the CSV file to read.
        - columns: column name, or list of column names, to histogram. Each must
            be numeric. Non-numeric values are dropped with a warning).
        - bins: number of histogram bins, shared across all subplots.
        - ncols: number of subplot columns in the grid; rows are added as needed.
        - figsize_per_plot: (width, height) in inches allotted to each subplot.
        - save_path: if given, the figure is saved to this path (parent directories
            are created as needed); otherwise the figure is just returned for
            display.

    Returns the matplotlib Figure.
    """
    if isinstance(columns, str):
        columns = [columns]

    df = pd.read_csv(csv_path)
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"Column(s) not found in {csv_path}: {missing}")

    nrows = math.ceil(len(columns) / ncols)
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(figsize_per_plot[0] * ncols, figsize_per_plot[1] * nrows),
        squeeze=False,
        facecolor=CHART_SURFACE,
    )
    axes_flat = axes.flatten()

    for i, column in enumerate(columns):
        ax = axes_flat[i]
        color = CATEGORICAL_PALETTE[i % len(CATEGORICAL_PALETTE)]

        values = pd.to_numeric(df[column], errors="coerce").dropna()
        dropped = len(df[column]) - len(values)
        if dropped:
            print(f"Warning: dropped {dropped} non-numeric value(s) in '{column}'")

        ax.set_facecolor(CHART_SURFACE)
        ax.hist(values, bins=bins, color=color, edgecolor=CHART_SURFACE, linewidth=0.5)
        if (values == values.round()).all():
            # Whole-number column (e.g. a count like Indegree/Outdegree): force
            # integer x-tick labels. Without this, matplotlib's automatic
            # locator picks a "nice" step from each subplot's own value range
            # in isolation, so a narrow-range integer column can get
            # fractional ticks (e.g. steps of 0.5) while a wider-range one
            # gets whole ones -- making same-format columns look like they
            # differ in dtype.
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_title(column, color=PRIMARY_INK, fontsize=11)
        ax.set_xlabel(column, color=MUTED_INK, fontsize=9)
        ax.set_ylabel("count", color=MUTED_INK, fontsize=9)
        ax.tick_params(colors=MUTED_INK, labelsize=8)
        ax.grid(axis="y", color=GRIDLINE, linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)
        for spine_name, spine in ax.spines.items():
            if spine_name in ("top", "right"):
                spine.set_visible(False)
            else:
                spine.set_color(BASELINE)

    # hide any unused subplot cells (e.g. 5 columns in a 2x3 grid)
    for ax in axes_flat[len(columns) :]:
        ax.set_visible(False)

    fig.tight_layout()

    if save_path is not None:
        save_path = Path(save_path).expanduser()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, facecolor=CHART_SURFACE, dpi=150)
        print(f"Saved to {save_path}")

    return fig


def plot_column_histograms_comparison(
    csv_paths: list[str],
    columns: str | list[str],
    labels: list[str] | None = None,
    bins: int = 30,
    ncols: int = 1,
    figsize_per_plot: tuple[float, float] = (4, 3),
    alpha: float = 0.75,
    save_path: str | Path | None = None,
):
    """Compare histograms of the same column(s) across multiple CSV files.

    Like plot_column_histograms, each column gets its own small-multiple
    subplot, but within a subplot the histograms from every CSV file are
    overlaid (semi-transparent, shared bin edges) so distributions can be
    compared directly. Files are distinguished by color and a legend.

    Args:
        - csv_paths: paths to the CSV files to compare.
        - columns: column name, or list of column names, to histogram. Each
            must be numeric in every file. Non-numeric values are dropped
            with a warning.
        - labels: legend label for each CSV file, in the same order as
            csv_paths. Defaults to each file's stem (filename without
            extension).
        - bins: number of histogram bins. Shared bin edges are computed per
            column from the combined range across all files, so bars line up.
        - ncols: number of subplot columns in the grid; rows are added as needed.
        - figsize_per_plot: (width, height) in inches allotted to each subplot.
        - alpha: opacity of each overlaid histogram, so overlapping bars stay
            legible.
        - save_path: if given, the figure is saved to this path (parent
            directories are created as needed); otherwise the figure is just
            returned for display.

    Returns the matplotlib Figure.
    """
    if isinstance(columns, str):
        columns = [columns]

    if labels is None:
        labels = [Path(p).stem for p in csv_paths]
    if len(labels) != len(csv_paths):
        raise ValueError("labels must have the same length as csv_paths")

    dfs = [pd.read_csv(p) for p in csv_paths]
    for path, df in zip(csv_paths, dfs):
        missing = [c for c in columns if c not in df.columns]
        if missing:
            raise ValueError(f"Column(s) not found in {path}: {missing}")

    nrows = math.ceil(len(columns) / ncols)
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(figsize_per_plot[0] * ncols, figsize_per_plot[1] * nrows),
        squeeze=False,
        facecolor=CHART_SURFACE,
    )
    axes_flat = axes.flatten()

    for i, column in enumerate(columns):
        ax = axes_flat[i]

        series_per_file = []
        for path, df in zip(csv_paths, dfs):
            values = pd.to_numeric(df[column], errors="coerce").dropna()
            dropped = len(df[column]) - len(values)
            if dropped:
                print(
                    f"Warning: dropped {dropped} non-numeric value(s) in '{column}' ({path})"
                )
            series_per_file.append(values)

        # shared bin edges so the same column is comparable across files
        all_values = pd.concat(series_per_file)
        bin_edges = (
            pd.cut(all_values, bins=bins, retbins=True)[1] if len(all_values) else bins
        )

        ax.set_facecolor(CHART_SURFACE)
        for j, values in enumerate(series_per_file):
            color = CATEGORICAL_PALETTE[j % len(CATEGORICAL_PALETTE)]
            ax.hist(
                values,
                bins=bin_edges,
                color=color,
                edgecolor=PRIMARY_INK,
                alpha=alpha,
                linewidth=0.7,
                label=labels[j],
            )
        if (all_values == all_values.round()).all():
            # see plot_column_histograms for why this is forced explicitly
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_title(column, color=PRIMARY_INK, fontsize=11)
        ax.set_xlabel(column, color=MUTED_INK, fontsize=9)
        ax.set_ylabel("count", color=MUTED_INK, fontsize=9)
        ax.tick_params(colors=MUTED_INK, labelsize=8)
        ax.grid(axis="y", color=GRIDLINE, linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)
        ax.legend(fontsize=8, labelcolor=MUTED_INK, frameon=False)
        for spine_name, spine in ax.spines.items():
            if spine_name in ("top", "right"):
                spine.set_visible(False)
            else:
                spine.set_color(BASELINE)

    # hide any unused subplot cells (e.g. 5 columns in a 2x3 grid)
    for ax in axes_flat[len(columns) :]:
        ax.set_visible(False)

    fig.tight_layout()

    if save_path is not None:
        save_path = Path(save_path).expanduser()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, facecolor=CHART_SURFACE, dpi=150)
        print(f"Saved to {save_path}")

    return fig


if __name__ == "__main__":
    fig = plot_column_histograms_comparison(
        csv_paths=[
            "plots/simple_mario_node_table.csv",
            "plots/simple_mario_pygraft_node_table.csv",
        ],
        columns=["Indegree", "Outdegree"],
        labels=["Real KG", "Synthetic KG"],
        bins=20,
        ncols=2,
        save_path="Degree_histogram_comparison.png",
    )
