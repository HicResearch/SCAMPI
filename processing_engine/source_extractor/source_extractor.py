import yaml
import os
from pydicom.dataset import Dataset
from pynetdicom import AE
from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelMove
import subprocess
import datetime
import pathlib


def source_extractor(config, logger):
    for name, source in config['sources'].items():
        if source['type'] == 'filesystem':
            if not os.path.isdir(source['directory']):
                logger.warn({
                    "message":source['directory'] + 'does not exist. Skipping',
                    "timestamp": datetime.datetime.now(datetime.UTC).timestamp()
                })
                continue
            _, _, files = next(os.walk(source['directory']))
            logger.info({
                "message":f'found {len(files)} files in {name} directory',
                "timestamp": datetime.datetime.now(datetime.UTC).timestamp()
            })
            continue;
        if source['type'] == 'pacs':
            #fetch the matching files and write them somewhere
            OUTPUT_DIR = Path("./received_dicoms/"+name)
            OUTPUT_DIR.mkdir(exist_ok=True)
            aet = source["aet"]
            aec = source["aec"]
            aem = source["aem"]
            pdu = source["pdu"]
            ip = source["ip"]
            port = source["port"]
            keys = source["keys"]
            pdu = source["pdu"]
            store_port = source['store_port']
            key_string = ""
            if len(keys) >0:
                key_string = f"-k {keys.join(' -k ')}"
            try:
                subprocess.Popen(f"python -m pynetdicom movescvu -aet {aet} -aec {aec} -aem {aem} -S --od {OUTPUT_DIR} --store --store-port{store_port} -pdu {pdu} {ip} {port} {key_string}")##TODO logging
            except Exception as e:
                logger.error({
                    "message": f"Error occurred while fetching files from {name}: {e}",
                    "timestamp": datetime.datetime.now(datetime.UTC).timestamp()
                })
            continue;
