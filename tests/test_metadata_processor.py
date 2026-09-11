import os
from unittest.mock import Mock

import pydicom
import yaml
from pydicom.dataset import FileDataset

from metadata_processor import metadata_processor


def write_dicom(path):
    file_meta = pydicom.dataset.FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.CTImageStorage
    file_meta.MediaStorageSOPInstanceUID = "1.2.3.4"
    file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    dataset = FileDataset(path, {}, file_meta=file_meta, preamble=b"\0" * 128)
    dataset.Modality = "CT"
    dataset.PatientID = "patient-123"
    dataset.StudyInstanceUID = "1.2.3"
    dataset.save_as(path)


def test_process_extracts_values_from_dicom_and_template(tmp_path, monkeypatch):
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template = {
        "Tables": [
            {
                "TableName": "StudyTable",
                "Columns": [
                    {"ColumnName": "PatientID"},
                    {"ColumnName": "StudyInstanceUID"},
                    {"ColumnName": "RelativeFileArchiveURI"},
                ],
            }
        ]
    }
    (template_dir / "CT.IT").write_text(yaml.safe_dump(template), encoding="utf-8")
    dicom_path = tmp_path / "image.dcm"
    write_dicom(dicom_path)
    logger = Mock()

    monkeypatch.setattr(metadata_processor, "modality_templates_location", str(template_dir))
    metadata_processor.modality_configs.clear()
    metadata_processor.modality_tables.clear()

    records = metadata_processor.process("image.dcm", str(tmp_path), logger)

    assert len(records) == 1
    values, modality, table_name = records[0]
    assert values[:2] == ["patient-123", "1.2.3"]
    assert os.path.normpath(values[2]) == os.path.normpath(str(dicom_path))
    assert (modality, table_name) == ("CT", "StudyTable")
