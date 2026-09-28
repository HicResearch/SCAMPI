import os
import pathlib
import datetime
import threading
import re
from pydicom.dataset import Dataset
from pynetdicom import AE, evt, AllStoragePresentationContexts
from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelMove
import zipfile
import io
import py7zr

def _build_identifier(keys: list[str]) -> Dataset:
    """Parse ["Tag=value", ...] into a pydicom Dataset for C-MOVE."""
    ds = Dataset()
    for key in keys:
        tag_name, _, value = key.partition("=")
        print(tag_name,value)
        setattr(ds, tag_name.strip(), value.strip())
    return ds


def _cmove(aet, aec, aem, ip, port, store_port, identifier, output_dir, pdu, logger):
    """Python equivalent of:
      movescu -aet <aet> -aec <aec> -aem <aem> <ip> <port> -k <keys>
    """
    ae = AE(ae_title=aet)
    ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)

    for cx in AllStoragePresentationContexts:
        ae.add_supported_context(cx.abstract_syntax)

    if pdu:
        ae.maximum_pdu_size = int(pdu)

    received = []
    lock = threading.Lock()

    def handle_store(event):
        ds = event.dataset
        ds.file_meta = event.file_meta
        path = output_dir / f"{ds.SOPInstanceUID}.dcm"
        ds.save_as(path, write_like_original=False)
        with lock:
            received.append(path)
        return 0x0000

    storage_server = ae.start_server(
        ("0.0.0.0", store_port),
        block=False,
        evt_handlers=[(evt.EVT_C_STORE, handle_store)],
    )

    try:
        assoc = ae.associate(ip, port, ae_title=aec)
        if not assoc.is_established:
            logger.error({
                "message": f"Failed to associate with PACS {aec} at {ip}:{port}",
                "timestamp": datetime.datetime.now(datetime.UTC).timestamp(),
            })
            return received

        try:
            responses = assoc.send_c_move(
                identifier,
                aem,
                PatientRootQueryRetrieveInformationModelMove,
            )
            for status, sub_identifier in responses:
                if not hasattr(status, "Status"):
                    logger.error({
                        "message": (
                            "C-MOVE aborted by peer"
                        ),
                        "timestamp": datetime.datetime.now(datetime.UTC).timestamp(),
                    })
                    break
                if status.Status not in (0x0000, 0xFF00, 0xFF01):
                    logger.warning({
                        "message": f"C-MOVE status 0x{status.Status:04X}",
                        "timestamp": datetime.datetime.now(datetime.UTC).timestamp(),
                    })
        finally:
            assoc.release()
    finally:
        storage_server.shutdown()

    logger.info({
        "message": f"C-MOVE complete - received {len(received)} file(s) into {output_dir}",
        "timestamp": datetime.datetime.now(datetime.UTC).timestamp(),
        "recieved":len(received)
    })
    return received

def list_files_recursive(path):
    entries = []
    for entry in os.listdir(path):
        full_path = os.path.join(path, entry)
        if os.path.isdir(full_path):
            entries.extend(list_files_recursive(full_path))
        else:
            entries.append(full_path)
    return entries

def source_extractor(config, logger):
    for name, source in config['sources'].items():

        if source['type'] == 'filesystem':
            if not os.path.isdir(source['directory']):
                logger.warning({
                    "message": source['directory'] + ' does not exist. Skipping',
                    "timestamp": datetime.datetime.now(datetime.UTC).timestamp(),
                })
                continue
            included_extensions= ['dcm','DCM']
            archive_extraction_dir = None
            if(source.get("include_archives",None )is not None):
                included_extensions.append('7z')
                included_extensions.append('zip')
                archive_extraction_dir = pathlib.Path("./received_dicoms") / name
                archive_extraction_dir.mkdir(parents=True, exist_ok=True)
            file_names = [fn for fn in list_files_recursive(source['directory'])
              if any(fn.endswith(ext) for ext in included_extensions)]
            file_regex = source.get("file_regex",None)
            if(file_regex is not None):
                file_names = [fn for fn in file_names if re.match(f'{file_regex}', os.path.basename(fn))]
            if archive_extraction_dir is not None:
                for file in file_names:
                    if file.endswith('.7z'):
                        with py7zr.SevenZipFile(file, mode='r') as archive:
                            archive.extractall(path=os.path.join(archive_extraction_dir, os.path.basename(file)))
                    if(file.endswith('.zip')):
                        zip_extract_dir = os.path.join(archive_extraction_dir, os.path.basename(file))
                        os.makedirs(zip_extract_dir, exist_ok=True)
                        with zipfile.ZipFile(file, 'r') as zf:
                            for member in zf.namelist():
                                if member.lower().endswith('.dcm'):
                                    zf.extract(member, zip_extract_dir)
            logger.info({
                "message": f"found {len(file_names)} files in {name} directory",
                "timestamp": datetime.datetime.now(datetime.UTC).timestamp(),
            })
            continue

        if source['type'] == 'pacs':
            output_dir = pathlib.Path("./received_dicoms") / name
            output_dir.mkdir(parents=True, exist_ok=True)
            identifier = _build_identifier(source.get("keys", []))

            _cmove(
                aet=source["aet"],
                aec=source["aec"],
                aem=source["aem"],
                ip=source["ip"],
                port=source["port"],
                store_port=source.get("store_port", 11113),
                identifier=identifier,
                output_dir=output_dir,
                pdu=source.get("pdu"),
                logger=logger,
            )
            continue
