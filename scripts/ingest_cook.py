"""Cook et al. 2019 ingestion stub (M1 stretch / M2).

Whole-animal connectomes (herm. + male) live on wormwiring.org under the paper's
source-data terms (Nature 2019, doi:10.1038/s41586-019-1352-7). Do NOT scrape blindly:
1. visit https://wormwiring.org, accept terms, download the hermaphrodite/male edge lists
2. place them in data/raw/cook2019/
3. extend this stub to normalise into data/processed/c_elegans_cook2019_v1.json
   using the common schema (see docs/datasets.md), then register counts here.
"""
print(__doc__)
