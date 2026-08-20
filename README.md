# SCAMPI
Scalable Clinical Imaging Processing and Management


```
 docker run --mount type=bind,src=C:\Users\jfriel001\git\SCAMPI\processing_engine/sample_config.yml,dst=/config.yml --mount type=bind,src=C:\Users\jfriel001\Downloads\ct-lung-screening-nlst-series,dst=/my_images  --mount type=bind,src=C:\Users\jfriel001\git\SCAMPI\processing_engine/Templates,dst=/templates  sha256:11fcd6d99e1c45dc6e46b98db02c189240dfd726d78316be263c6337e02f0efe
```