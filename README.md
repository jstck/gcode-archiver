## G-code Archiver for Moonraker

A small Python CLI that queries a Moonraker server for `gcode_metadata`, keeps the N most recent G-code files, and prints or executes moves to archive the rest.

### Requirements

- Python 3.8+

### How it works

- Fetches `gcode_metadata` from Moonraker at `http://<host>:<port><endpoint>`.
- Computes recency per file as `max(modified, print_start_time)`.
- Keeps the most recent `--keep` files; the rest are listed for archiving.
- By default, prints dry-run `mv -n` commands from `--gcode-dir` to `--archive-dir`.
- With `--execute`, creates destination directories as needed and moves files.

### Usage

```bash
python3 fetch_gcode_metadata.py \
  --host localhost \
  --port 7125 \
  --endpoint /server/database/item?namespace=gcode_metadata \
  --keep 12 \
  --gcode-dir ~/printer_data/gcode \
  --archive-dir ~/printer_data/gcode/archive
```

- To actually move files (instead of printing the commands):

```bash
python3 fetch_gcode_metadata.py --keep 12 --execute
```

### Arguments

- `--host` (default: `localhost`): Moonraker host
- `--port` (default: `7125`): Moonraker port
- `--endpoint` (default: `/server/database/item?namespace=gcode_metadata`): API path
- `--timeout` (default: `10`): HTTP timeout in seconds
- `--keep` (default: `12`): Number of most recent files to keep
- `--gcode-dir` (default: `~/printer_data/gcode`): Source directory of `.gcode` files
- `--archive-dir` (default: `~/printer_data/gcode/archive`): Destination directory for archived files
- `--execute` (flag): Perform moves; otherwise only print `mv -n` commands

### Notes

- Unknown timestamps are treated as least recent (they get archived first).
- Moves use Python `shutil.move` (cross-filesystem safe). Dry-run output uses `mv -n` for clarity.


