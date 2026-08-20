import yaml
import os
import pydicom
import numpy as np
import pandas as pd
from destination_writer.destination_writer import destination_writer
import traceback
import time
# templates from https://github.com/SMI/DicomTypeTranslation/tree/main/Templates
modality_templates_location="/templates"

config = None

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
        pks = []##todo do something with this
        columns = table['Columns']
        for column in columns:
            df.insert(df.size,column['ColumnName'],[]) 
            is_pk = column.get('IsPrimaryKey',False)
            if is_pk:
                pks.append(column['ColumnName'])
            #todo allow nulls
            #todo type
            # column_type = column.get('Type',None)
            # if column_type is not None:
            #     if column_type["CSharpType"] == 'System.Int64':                
            #     if column_type["CSharpType"] == 'System.String':                
            #     if column_type["CSharpType"] == 'System.Decimal':                
            #     if column_type["CSharpType"] == 'System.Double':                
            #     if column_type["CSharpType"] == 'System.Date':                
        modality_tables[modality + '_'+table['TableName']]  = df# e.g. CT_StudyTable, CT_SeriesTable, CT_ImageTable
    return modality_tables.get(modality+'_'+table_name,None)

def metadata_processor():
    start_time = time.time()
    with open("/config.yml") as ymlstream:
        try:
            config  = yaml.safe_load(ymlstream)
        except yaml.YAMLError as exc:
            # print(exc)
            raise RuntimeError(exc)

    file_count=0


    for name, source in config['sources'].items():
        root_directory = None
        if source['type'] == 'filesystem':
            if not os.path.isdir(source['directory']):
                print(source['directory'] + 'does not exist. Skipping')
                continue
            root_directory =source['directory']
        if source['type'] == 'pacs':
            print("PACS Not Implemented")
            root_directory = "./received_dicoms/"+name
        for file in os.listdir(root_directory):
            filename = os.fsdecode(file)
            if filename.endswith('.dcm'):
                file_count = file_count+1
                ds = pydicom.dcmread(root_directory +'/'+filename)
                try:
                    modality = ds.Modality
                    modality_config = get_modality_config_for_file(modality)
                    if modality_config is None:
                        print("modality not found", modality)
                        continue

                    tables = modality_config["Tables"]
                    for table in tables:
                        modality_table = get_modality_table(modality,table['TableName']) #return a df with the correct columns
                        record = []
                        for column in table["Columns"]:
                            if '_' in column["ColumnName"]:
                                #sequence todo
                                # print('todo')
                                record.append(None)
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
                        
                        modality_table.loc[modality_table.shape[0]] = record
                        modality_tables[modality+'_'+table['TableName']] = modality_table
                except Exception as e:
                    print(e,traceback.format_exc())
                    continue

    end_time = time.time()
    print("Processed ", file_count, " files in", end_time-start_time, "s (", (end_time-start_time)/file_count,"s avg)")
    for key,value in modality_tables.items():
        destination_writer(key,value)


