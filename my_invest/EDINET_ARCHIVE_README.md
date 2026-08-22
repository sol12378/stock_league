# EDINET full raw archive

`edinet_full_archive.py` stores EDINET API responses without transforming their bytes. The API key is read only from `stock_league/.env`; it is never printed or stored in the SQLite manifest.

## Archive layout

- `data/raw/edinet_full/daily_lists/`: original daily list JSON
- `data/raw/edinet_full/documents/`: type 1-5 document payloads
- `data/raw/edinet_full/public_assets/`: taxonomies, code lists and official specifications
- `data/raw/edinet_full/manifest/archive.sqlite3`: hashes, sizes, status and metadata
- `outputs/edinet_full_archive/`: progress audit

## Commands

```bash
python edinet_full_archive.py init
python edinet_full_archive.py import-existing --mode hardlink
python edinet_full_archive.py scan --start 2016-08-18 --end 2026-08-18
python edinet_full_archive.py assets
python edinet_full_archive.py download --types 1,3,4 --reserve-gib 60
python edinet_full_archive.py download --types 2,5 --reserve-gib 60
python edinet_full_archive.py audit
```

All commands are idempotent and resumable. `.part` files are atomically renamed only after ZIP/PDF validation. A payload with status `ok` is skipped on later runs.

For an unattended, capacity-guarded continuation in research-value order, run:

```bash
./continue_edinet_archive.sh
```

The script keeps 60 GiB free and stops safely if the current volume cannot hold the remaining originals. See `outputs/edinet_full_archive/archive_capacity_plan_20260818.md` for the measured storage estimate and `outputs/double_stock_research_master_plan_20260818.md` for the point-in-time research design.
