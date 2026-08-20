import yaml
import os
from pydicom.dataset import Dataset
from pynetdicom import AE
from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelMove
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
            print("PACS Not Implemented")
            #fetch the matching files and write them somewhere
            # OUTPUT_DIR = Path("./received_dicoms/"+name)
            # OUTPUT_DIR.mkdir(exist_ok=True)

            # def handle_store(event):
            #     """Handle incoming C-STORE requests."""

            #     ds = event.dataset
            #     ds.file_meta = event.file_meta

            #     filename = OUTPUT_DIR / f"{ds.SOPInstanceUID}.dcm"

            #     ds.save_as(filename, write_like_original=False)

            #     print(f"Received: {filename}")

            #     return 0x0000

            # ae = AE(ae_title="MY_AE")

            # # We are a C-MOVE SCU
            # ae.add_requested_context(
            #     PatientRootQueryRetrieveInformationModelMove
            # )

            # # We are also a Storage SCP
            # ae.supported_contexts = StoragePresentationContexts


            # # --------------------------------------------------
            # # Start local Storage SCP
            # # --------------------------------------------------

            # handlers = [
            #     (evt.EVT_C_STORE, handle_store),
            # ]

            # scp = ae.start_server(
            #     ("0.0.0.0", 11113),
            #     block=False,
            #     evt_handlers=handlers,
            # )

            # print("Storage SCP listening on port 11113")
            # # --------------------------------------------------
            # # Create C-MOVE query
            # # --------------------------------------------------

            # ds = Dataset()
            # ds.QueryRetrieveLevel = "SERIES"
            # ds.PatientID = "1234567"
            # ds.StudyInstanceUID = "1.2.3"
            # ds.SeriesInstanceUID = "1.2.3.4"


            # # --------------------------------------------------
            # # Connect to PACS
            # # --------------------------------------------------

            # assoc = ae.associate(
            #     "192.168.1.100",
            #     11112,
            #     ae_title="PACS",
            # )

            # if not assoc.is_established:
            #     raise RuntimeError("Could not connect to PACS")


            # # --------------------------------------------------
            # # Perform C-MOVE
            # # --------------------------------------------------

            # responses = assoc.send_c_move(
            #     ds,
            #     "MY_AE",
            #     PatientRootQueryRetrieveInformationModelMove,
            # )

            # for status, identifier in responses:

            #     if status is None:
            #         print("C-MOVE failed: no status received")
            #         continue

            #     print(
            #         f"Status: 0x{status.Status:04X}, "
            #         f"remaining={getattr(status, 'NumberOfRemainingSuboperations', '?')}, "
            #         f"completed={getattr(status, 'NumberOfCompletedSuboperations', '?')}, "
            #         f"failed={getattr(status, 'NumberOfFailedSuboperations', '?')}"
            #     )


            # assoc.release()

            # # Stop Storage SCP
            # scp.shutdown()
            continue;
