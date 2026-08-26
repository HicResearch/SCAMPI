import yaml
import os
from pydicom.dataset import Dataset
from pynetdicom import AE
from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelMove
import subprocess
config = None


def source_extractor():
    with open("/config.yml") as ymlstream:
        try:
            config  = yaml.safe_load(ymlstream)
        except yaml.YAMLError as exc:
            print(exc)
            return

    for name, source in config['sources'].items():
        if source['type'] == 'filesystem':
            if not os.path.isdir(source['directory']):
                print(source['directory'] + 'does not exist. Skipping')
                continue
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
            os.popen(f"python -m pynetdicom movescvu -aet {aet} -aec {aec} -aem {aem} -S --od {OUTPUT_DIR} --store --store-port{store_port} -pdu {pdu} {ip} {port} {key_string}")
            continue;
