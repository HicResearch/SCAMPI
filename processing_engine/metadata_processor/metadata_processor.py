import yaml
import os
import pydicom
import numpy as np
import pandas as pd
from destination_writer.destination_writer import destination_writer
import traceback
import time
import datetime
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from itertools import repeat
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
            df.insert(df.size,column['ColumnName'],[]) 
            column_type = column.get('Type',None)
            if column_type is not None:
                if column_type["CSharpType"] == 'System.Int64':                
                    df[column["ColumnName"]] = pd.to_numeric(df[column["ColumnName"]])
                # if column_type["CSharpType"] == 'System.String':  
                #     df[column["ColumnName"]] = pd.to_string(df[column["ColumnName"]])              
                if column_type["CSharpType"] == 'System.Decimal':                
                    df[column["ColumnName"]] =  df[column["ColumnName"]].astype(float)
                if column_type["CSharpType"] == 'System.Double':                
                    df[column["ColumnName"]] = df[column["ColumnName"]].astype(float)
                if column_type["CSharpType"] == 'System.Date':     
                    df[column["ColumnName"]] = pd.to_datetime(df[column["ColumnName"]])
            ##TODO
            # is_pk = column.get('IsPrimaryKey',False)
            # if is_pk:
            #     pks.append(column['ColumnName'])
        modality_tables[modality + '_'+table['TableName']]  = df# e.g. CT_StudyTable, CT_SeriesTable, CT_ImageTable
    return modality_tables.get(modality+'_'+table_name,None)


def process(file,root_directory, logger):
    filename = os.fsdecode(file)
    records = []
    if filename.endswith('.dcm'):
        ds = pydicom.dcmread(root_directory +'/'+filename, stop_before_pixels=True)
        try:
            modality = ds.Modality
            modality_config = get_modality_config_for_file(modality)
            if modality_config is None:
                logger.error({
                    "message":f'modality {modality} not found',
                    "timestamp": datetime.datetime.now(datetime.UTC).timestamp(),
                    "modality":modality
                })
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
                    else:
                        if column["ColumnName"] == "RelativeFileArchiveURI":
                            record.append(root_directory +'/'+filename)
                            continue
                        try:
                            data_element = ds.data_element(column["ColumnName"])
                            if data_element is None:
                                record.append(None)
                            else:
                                record.append(data_element.value)
                        except Exception as e:
                            record.append(None)
                records.append((record,modality,table['TableName']))
        except Exception as e:
            print(e,traceback.format_exc())
            logger.error({
                "message":e,
                "timestamp": datetime.datetime.now(datetime.UTC).timestamp()
            })
        return records


def metadata_processor(config, logger):
    start_time = time.time()
    logger.debug({
        "message":'Starting metadata processing',
        "timestamp": datetime.datetime.now(datetime.UTC).timestamp()
    })

    file_count=0

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
            for result in list(executor.map(process, os.listdir(root_directory),repeat(root_directory), repeat(logger))):
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
        "message":"Processed "+ str(file_count) + " files in " + str(end_time-start_time) + "s (" + str((end_time-start_time)/file_count) +'s avg)',
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


