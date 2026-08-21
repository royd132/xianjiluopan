$ErrorActionPreference = "Stop"

python scripts/data/download_fx.py
python scripts/data/download_gscpi.py
python scripts/data/download_world_bank_shipping.py
python scripts/data/download_comtrade.py
python scripts/data/download_amazon_samples.py
python scripts/data/download_amazon_metadata_sample.py
python scripts/data/download_amazon_matched_reviews.py
python scripts/data/download_multilingual_reviews.py
python scripts/data/download_olist.py
python scripts/data/verify_datasets.py
