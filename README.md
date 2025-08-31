## G-code Archiver for Moonraker

A small Python CLI that queries a Moonraker server for `gcode_metadata`, keeps the N most recent G-code files, and prints or executes moves to archive the rest.

### Requirements

- Python 3.8+

### How it works

- Fetches `gcode_metadata` from Moonraker at `http://<host>:<port><endpoint>`.
- Computes recency per file as `max(modified, print_start_time)`.
- Keeps the most recent `--keep` files; the rest are listed for archiving.
- By default, executes moves from `--gcode-dir` to `--archive-dir`.
- With `--dry-run`, prints `mv -n` commands without making changes.
- With `--verbose`, prints detailed keep/archive listings and move summary.

### Usage

```bash
python3 fetch_gcode_metadata.py \
  --host localhost \
  --port 7125 \
  --endpoint /server/database/item?namespace=gcode_metadata \
  --keep 42 \
  --gcode-dir ~/printer_data/gcode \
  --archive-dir ~/printer_data/gcode/archive
```

- To preview commands without moving files:

```bash
python3 fetch_gcode_metadata.py --keep 42 --dry-run
```

### Arguments

- `--host` (default: `localhost`): Moonraker host
- `--port` (default: `7125`): Moonraker port
- `--endpoint` (default: `/server/database/item?namespace=gcode_metadata`): API path
- `--timeout` (default: `10`): HTTP timeout in seconds
- `--keep` (default: `42`): Number of most recent files to keep
- `--gcode-dir` (default: `~/printer_data/gcode`): Source directory of `.gcode` files
- `--archive-dir` (default: `~/printer_data/gcode/archive`): Destination directory for archived files
- `--dry-run` (flag): Print `mv -n` commands; otherwise perform moves
- `--verbose` (flag): Print detailed keep/archive listing and messages

### Notes

- Unknown timestamps are treated as least recent (they get archived first).
- Moves use Python `shutil.move` (cross-filesystem safe). Dry-run output uses `mv -n` for clarity.


