# SCAMPI
Scalable Clinical Imaging Processing and Management


```
docker run -v C:\Users\jfriel001\git\SCAMPI\processing_engine/logs:/SCAMPI/logs --mount type=bind,src=C:\Users\jfriel001\git\SCAMPI\processing_engine/sample_config.yml,dst=/config.yml --mount type=bind,src=C:\Users\jfriel001\Downloads\ct-lung-screening-nlst-series,dst=/my_images  --mount type=bind,src=C:\Users\jfriel001\git\SCAMPI\processing_engine/Templates,dst=/templates sha256:a0ad3a68e012ba508b08493e37b71fc99c5a6482ceb20ac0154fca16c9a91272
```