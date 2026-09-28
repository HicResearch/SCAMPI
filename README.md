![Tests](https://github.com/HicResearch/SCAMPI/actions/workflows/tests.yml/badge.svg)
![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/JFriel/ef302fe4cee3248c4974297ba157016c/raw/scampi_coverage.json)
![Docker Hub](https://img.shields.io/docker/v/taggenblu/scampi)

# SCAMPI

SCAMPI is a DICOM processing engine that extracts DICOM files from a source (local filesystem or PACS server), reads their metadata, and writes the metadata to a SQL Server database alongside copying the files to an output directory.

## Prerequisites

- Docker
- A running SQL Server instance accessible from the container
- DICOM source: either a local directory of `.dcm` files or a reachable PACS server

## Configuration

Copy `processing_engine/sample_config.yml` to `config.yml` and edit it before running.

```yaml
sources:
  my_source:                      # arbitrary name for this source
    type: filesystem              # "filesystem" or "pacs"
    directory: /my_images         # path inside the container (see volume mounts below)
    file_regex: .*                # optional: filter filenames by regex
    include_archives: True        # optional: also process .7z archives
  pacs_source:
    type: pacs
    aet: LOCALMACHINE           # your calling AE title
    aec: ORTHANC                # called AE title (the PACS)
    aem: LOCALMACHINE           # move destination AE title
    ip: 192.168.1.10
    port: 4242
    store_port: 11113           # port SCAMPI listens on for incoming C-STORE
    keys:
      - "QueryRetrieveLevel=STUDY"
      - "StudyInstanceUID=1.2.3..."

destination:
  files:
    directory: /output            # path inside the container (see volume mounts below)
    compress: true
  metadata:
    dbType: MSSQL
    connectionString: mssql+pyodbc://user:pass@host.docker.internal,1433/SCAMPI?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
    index: some_column
```

Use `host.docker.internal` as the hostname to reach SQL Server running on the Docker host machine.

## Building the Docker image

Run from the repository root:

```bash
docker build -t scampi -f processing_engine/Dockerfile processing_engine/
```

## Running the container

```bash
docker run --rm \
  -v /path/to/your/config.yml:/config.yml \
  -v /path/to/dicoms:/my_images \
  -v /path/to/output:/output \
  -v /path/to/templates:/templates \
  -v /path/to/logs:/SCAMPI/logs \
  scampi
```

| Mount | Purpose |
|---|---|
| `config.yml:/config.yml` | Required. Your configuration file. |
| `dicoms:/my_images` | Required for `filesystem` sources. Must match `directory` in config. |
| `output:/output` | Required. Where processed DICOM files are written. Must match `destination.files.directory` in config. |
| `templates:/templates` | Required. A directory with modality.it config files. See [DICOMTypeTranslater](https://github.com/SMI/DicomTypeTranslation/tree/main/Templates) |
| `logs:/SCAMPI/logs` | Optional. Persists log files to the host. |

For PACS sources, no filesystem source mount is needed, but the container must have network access to the PACS server on the configured `ip` and `port`.

### Windows paths

On Windows, use the full path with forward slashes or escape backslashes:

```bash
docker run --rm \
  -v C:/Users/you/config.yml:/config.yml \
  -v C:/Users/you/dicoms:/my_images \
  -v C:/Users/you/output:/output \
  scampi
```

## Logs

Log files are written to `/SCAMPI/logs/` inside the container (mount this path to retain them). Structured JSON logs are also printed to stdout, so `docker logs <container>` works for live output.
