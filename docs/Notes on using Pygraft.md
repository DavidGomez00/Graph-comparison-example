# Generate synthetic KG using PyGraft from .data/{name}/{real_graph}.tsv

To generate a synthetic KG using PyGraft, we have to hand craft a set of files:
 - `output/{name}/schema.rdf`: Defines the schema of the graph.
 - `output/{name}/class_info.json`: Defines the classes in the KG.
 - `output/{name}/relation_info.json`: Defines the relations in the KG.

PyGraft names classes/relations generically (`C1`, `R1`...`R5`). The auto-generated schema was kept as `output/{name}/generated_schema.rdf` for reference, then hand-customized into `output/{name}/schema.rdf`, along with matching `output/{name}/class_info.json` and `output/{name}/relation_info.json`, loaded directly by `generate_kg`:
 - relations renamed to the real ones.
 - one spurious `rdfs:subPropertyOf` dropped (a PyGraft library artifact, not a real characteristic of the data)