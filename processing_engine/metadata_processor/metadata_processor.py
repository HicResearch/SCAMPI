import yaml
import os
import pydicom
import numpy as np
import pandas as pd
from destination_writer.destination_writer import destination_writer
import time
import datetime
from concurrent.futures import ProcessPoolExecutor
from itertools import repeat
import re
# templates from https://github.com/SMI/DicomTypeTranslation/tree/main/Templates
modality_templates_location="/templates"


modality_configs = dict()
modality_tables = dict()

start_time = None
end_time = None

def get_modality_config_for_file(modality):
    modality_config = modality_configs.get(modality,None)
    if modality_config is not None:
        return modality_config
    for file in os.listdir(modality_templates_location):
        filename = os.fsdecode(file)
        if filename.upper() == modality.upper()+'.IT':
            with open(modality_templates_location + '/'+filename) as configyml:
                try:
                    modality_config = yaml.safe_load(configyml)
                    modality_configs[modality] = modality_config
                    return modality_config
                except yaml.YAMLError as exc:
                    print('gmcff',exc)
                    return

def get_modality_table(modality,table_name):
    modality_table = modality_tables.get(modality+'_'+table_name,None)
    if(modality_table is not None):
        return modality_table

    modality_config = get_modality_config_for_file(modality)
    tables = modality_config["Tables"]
    for table in tables:
        df = pd.DataFrame()
        columns = table['Columns']
        for column in columns:
            df[column['ColumnName']] = None
        modality_tables[modality + '_'+table['TableName']]  = df# e.g. CT_StudyTable, CT_SeriesTable, CT_ImageTable
    return modality_tables.get(modality+'_'+table_name,None)


def _datasetProcess(ds,root_directory,filename,logger):
    records = []
    modality = None
    modality_config = None
    try:
        modality = ds.Modality
        modality_config = get_modality_config_for_file(modality)
    except Exception:
        pass
    if modality_config is None:
        logger.error({
            "message":f'modality {modality} not found',
            "timestamp": datetime.datetime.now(datetime.UTC).timestamp(),
            "modality":modality
        })
        #return records
        modality = 'OTHER'
        modality_config = get_modality_config_for_file('OTHER')
        if modality_config is None:
            return records

    tables = modality_config["Tables"]
    for table in tables:
        modality_table = get_modality_table(modality,table['TableName']) #return a df with the correct columns
        record = []
        for column in table["Columns"]:
            if '_' in column["ColumnName"]:
                dcm_path = column["ColumnName"].split('_')
                data_element = None
                try:
                    for path_element in dcm_path:
                        if  data_element is None:
                            data_element = ds.data_element(path_element)
                        else: 
                            data_element = data_element.data_element(path_element)
                        if data_element is None:
                            break
                except Exception as e:
                    logger.error({
                        "message":e,
                        "timestamp": datetime.datetime.now(datetime.UTC)
                    })
                if data_element is None:
                        record.append(None)
                else:
                    record.append(data_element.value)
                continue
            elif column["ColumnName"] == "RelativeFileArchiveURI":
                    record.append(root_directory +'/'+filename)
                    continue
            try:
                data_element = ds.data_element(column["ColumnName"])
                if data_element is None:
                    record.append(None)
                else:
                    record.append(guess_type_based_on_vr(data_element.value,data_element.VR))
            except Exception as e:
                record.append(None)
        records.append((record,modality,table['TableName']))
    return records


def guess_type_based_on_vr(value,type):
    match type:
        case 'DA':
            return pd.to_datetime(value)
        case 'FL':
            return float(value)
        case'FD':
            return float(value)
        case _:
            return str(value)


def get_file_names_from_directory_recursive(dir):
    filenames=[]
    for f in os.listdir(dir):
        if os.path.isdir(os.path.join(dir,f)):
            filenames = filenames + get_file_names_from_directory_recursive(os.path.join(dir,f))
        else:
            filenames.append(os.path.join(dir,f))
    return filenames

def process(file,root_directory,name, logger):
    filename = os.fsdecode(file)
    records = []
        
    if filename.endswith('.7z'):
        archive_extraction_dir = os.path.join("./received_dicoms",name,filename);
        for f in get_file_names_from_directory_recursive(archive_extraction_dir):
            try:
                ds = pydicom.dcmread(f, stop_before_pixels=True)
                records = records + _datasetProcess(ds,root_directory,filename+'!'+f.split(filename)[1][1:],logger)
            except Exception as e:
                continue
    else:
        try:
            ds = pydicom.dcmread(root_directory +'/'+filename, stop_before_pixels=True)
            records = _datasetProcess(ds,root_directory,filename,logger)
        except:
            pass
    return records


def metadata_processor(config, logger):
    start_time = time.time()
    logger.debug({
        "message":'Starting metadata processing',
        "timestamp": datetime.datetime.now(datetime.UTC).timestamp()
    })

    file_count=0
    file_regex = config.get("file_regex",None)
    include_archives = config.get("include_archives",None)
    for name, source in config['sources'].items():
        root_directory = None
        if source['type'] == 'filesystem':
            if not os.path.isdir(source['directory']):
                logger.warn({
                    "message":source['directory'] + 'does not exist. Skipping',
                    "timestamp": datetime.datetime.now(datetime.UTC).timestamp()
                })
                continue
            root_directory =source['directory']
        if source['type'] == 'pacs':
            root_directory = "./received_dicoms/"+name
        with ProcessPoolExecutor() as executor:
            records_by_table = {}
            files = None
            included_extensions= ['dcm','DCM']
            if(source.get("include_archives",None )is not None):
                included_extensions.append('7z')
                included_extensions.append('zip')

            if file_regex:
                files = [fn for fn in os.listdir(root_directory)
                if (any(fn.endswith(ext) for ext in included_extensions) or re.search(r".*\.[0-9]*$",fn)) and re.match(f'{file_regex}',fn)]
            else:   
                files = [fn for fn in os.listdir(root_directory)
                                if (any(fn.endswith(ext) for ext in included_extensions) or re.search(r".*\.[0-9]*$",fn))]
            for result in list(executor.map(process, files,repeat(root_directory),repeat(name), repeat(logger))):
                if result is not None:
                    for r in result:
                        if r is not None:
                            tr = records_by_table.get(r[1]+'_'+r[2],[])
                            tr.append(r[0])
                            records_by_table[r[1]+'_'+r[2]] = tr
                    file_count = file_count+1
            for key, rows in records_by_table.items():
                modality_table = get_modality_table(key.split('_')[0],key.split('_')[1])
                additional_records_dt = pd.DataFrame(rows, columns=modality_table.columns)
                modality_table = pd.concat([modality_table,additional_records_dt])
                modality_tables[key] = modality_table
    end_time = time.time()
    logger.info({
        "message":"Processed "+ str(file_count) + " files in " + str(end_time-start_time) + "s (" + str((end_time-start_time)/max(file_count,1)) +'s avg)',
        "timestamp": datetime.datetime.now(datetime.UTC).timestamp(),
        "file_count":file_count,
        "duration": end_time-start_time
    })
    logger.debug({
        "message":'Completed metadata processing',
        "timestamp": datetime.datetime.now(datetime.UTC).timestamp()
    })
    for key,value in modality_tables.items():
        destination_writer(config,logger,key,value)


