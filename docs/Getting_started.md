# Running AMIE3 for rule mining

The script `run_amie.py` shells out to a local AMIE3 `.jar`. This is `amie3.5.1.jar` by default, but you can use your own `.jar` specifying it with `--jar`. It requires a Java runtime on `PATH`. Download AMIE3 from the [AMIE repository](https://github.com/dig-team/amie).


`run_amie.py` is a thin CLI wrapper around AMIE3, invoked as a Java subprocess:

```bash
python run_amie.py .data/lung_cancer/lung_cancer.nt -o output/lung_cancer_rules.csv
```

AMIE3's plain-text stdout table is parsed and written out as CSV. AMIE's own defaults are what's used above, and they're fine here.

>Note: those same defaults are tuned for large knowledge bases and will silently mine zero (or only trivial) rules on a small or logically-thin graph. Run `python run_amie.py --help` for all options.

# Setup

Use `pip install -r requirements.txt` to install the neccessary dependencies.

Run the report generation script with `python topology_report.py`