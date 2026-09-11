import yaml

import pygraft
from utils import parse_result

schema_name = "office"
config_file = f"output/{schema_name}/{schema_name}.yml"

# pygraft.create_template()
# pygraft.generate_schema("template.yml")
pygraft.generate_kg(config_file)

# Parse resulted graph into .tsv and .ttl files. n_entities must cover the
# schema's full E1..E<num_entities> range (parse_result's own default of 15
# only works by coincidence for small schemas -- it would silently drop
# almost everything for a schema like french_royalty, with num_entities:
# 4429), so it's read from the same config passed to generate_kg above.
with open(config_file) as f:
    num_entities = yaml.safe_load(f)["num_entities"]

parse_result(
    full_graph=f"output/{schema_name}/full_graph.rdf",
    ttl_file=f".data/{schema_name}/{schema_name}_pygraft.ttl",
    tsv_file=f".data/{schema_name}/{schema_name}_pygraft.tsv",
    n_entities=num_entities + 1,
)
