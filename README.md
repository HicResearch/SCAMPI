# SCAMPI
Scalable Clinical Imaging Processing and Management


```
docker run -v C:\Users\jfriel001\git\SCAMPI\processing_engine/logs:/SCAMPI/logs --mount type=bind,src=C:\Users\jfriel001\git\SCAMPI\processing_engine/sample_config.yml,dst=/config.yml --mount type=bind,src=C:\Users\jfriel001\Downloads\ct-lung-screening-nlst-series,dst=/my_images  --mount type=bind,src=C:\Users\jfriel001\git\SCAMPI\processing_engine/Templates,dst=/templates --mount type=bind,src=C:\Users\jfriel001\git\SCAMPI\received_dicoms,dst=/output sha256:a0ad3a68e012ba508b08493e37b71fc99c5a6482ceb20ac0154fca16c9a91272
```

## Testing

Create or activate a Python virtual environment, install the development dependencies, and run the test suite from the repository root:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

The tests use temporary directories and synthetic DICOM files, so they do not require a PACS server, database, Docker, or the sample images.


## Code Coverage
```
.\venv\Scripts\python.exe -m pytest tests --cov=processing_engine --cov-report=term-missing --cov-branch
``
or fancy HTML
```
.\venv\Scripts\python.exe -m pytest tests --cov=processing_engine --cov-report=html
```