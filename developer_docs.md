# SCAMPI Developer Documentation

SCAMPI (Scalable Clinical Imaging Processing and Management) extracts DICOM files from a source (local filesystem or PACS server), reads their metadata according to per-modality templates, and writes the metadata to SQL Server alongside copying the files to an output directory.

## Repository layout

```
SCAMPI/
├── processing_engine/          # application code + Dockerfile
│   ├── process_engine.py       # entrypoint — loads config, runs the pipeline
│   ├── source_extractor/       # pull DICOMs from filesystem or PACS
│   ├── metadata_processor/     # extract DICOM tags → DataFrames via modality templates
│   ├── destination_writer/     # write files + metadata to SQL Server
│   ├── Dockerfile
│   └── requirements.txt
├── tests/                      # pytest test suite
├── test_images/                # sample .dcm files used by tests
├── pyproject.toml              # pytest config
├── requirements-dev.txt        # dev dependencies (includes requirements.txt)
└── instructions.md             # end-user / ops guide
```

## Architecture

The pipeline runs in three sequential stages:

```
config.yml
    │
    ▼
source_extractor      reads from filesystem or issues a DICOM C-MOVE from a PACS,
                      saving .dcm files into received_dicoms/<source_name>/
    │
    ▼
metadata_processor    for each .dcm file, looks up the modality template (.it),
                      extracts DICOM tag values into a pandas DataFrame per table,
                      then hands the DataFrames to destination_writer
    │
    ▼
destination_writer    copies .dcm files to the destination directory and writes
                      metadata rows to SQL Server via SQLAlchemy
```

## Setting up a development environment

Requires Python 3.13.

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements-dev.txt
```

`requirements-dev.txt` includes all runtime dependencies plus `pytest` and `pytest-cov`.

## Running the tests

Run from the repository root (where `pyproject.toml` is):

```bash
python -m pytest
```

`pyproject.toml` configures pytest to find tests in `tests/` and adds `processing_engine/` to `sys.path` so the source packages import without installation.

The tests use `tmp_path` and `monkeypatch` fixtures throughout and create synthetic DICOM files on the fly. A small set of real `.dcm` fixtures lives in `test_images/` for tests that need a valid file on disk. No PACS server, SQL Server, or Docker is required.

## Code coverage

Print a coverage summary with missed lines to the terminal:

```bash
python -m pytest tests --cov=processing_engine --cov-report=term-missing --cov-branch
```

Generate an HTML report (written to `htmlcov/index.html`):

```bash
python -m pytest tests --cov=processing_engine --cov-report=html --cov-branch
```

The `--cov-branch` flag enables branch coverage so conditional paths are tracked as well as line coverage.

## Test layout

| File | What it covers |
|---|---|
| `tests/test_source_extractor.py` | `_build_identifier`, `_cmove` (association, C-MOVE responses, storage SCP lifecycle), `source_extractor` (filesystem, PACS, archives, regex filtering) |
| `tests/test_metadata_processor.py` | Template loading/caching, DataFrame construction, `process` per-file extraction, the full `metadata_processor` orchestration |
| `tests/test_destination_writer.py` | `write_metadata` (MSSQL success/failure, unsupported db type), `write_file` (copy routing, None destination), `destination_writer` dispatcher |

## Key dependencies

| Package | Purpose |
|---|---|
| `pydicom` | Reading DICOM files |
| `pynetdicom` | PACS communication — issues C-MOVE and runs a storage SCP |
| `pandas` | Assembling extracted metadata into DataFrames |
| `SQLAlchemy` + `pyodbc` | Writing DataFrames to SQL Server via `DataFrame.to_sql` |
| `py7zr` | Extracting DICOM files from `.7z` archives |
| `python-json-logger` | Structured JSON log output |
| `PyYAML` | Parsing `config.yml` and modality template files |

## Logs

The application writes structured JSON logs. At runtime, log files are created at `/SCAMPI/logs/<timestamp>.log` inside the container. Log level is set to `DEBUG` in `process_engine.py`. To change it, adjust the `level` argument to `logging.basicConfig`.
