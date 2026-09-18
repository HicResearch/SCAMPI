import yaml
import datetime
import shutil
import os


def get_destination_location(row,destination):
    return os.path.join(destination,row['RelativeFileArchiveURI'].split('/')[-1])

def write_file(config,logger,dataframe):
    start_time = datetime.datetime.now(datetime.UTC)
    destination =  config['destination']['files']['directory']
    for _, row in dataframe.iterrows():
         if row.get("RelativeFileArchiveURI") is not None:
            destination_file = get_destination_location(row,destination)
            if destination_file is not None:
                shutil.copyfile(row['RelativeFileArchiveURI'],destination_file)
    end_time = datetime.datetime.now(datetime.UTC)
    logger.info({
        "message":f"Wrote {len(dataframe.index)} files in {(end_time-start_time).total_seconds()} seconds",
        "timestamp": datetime.datetime.now(datetime.UTC).timestamp()
    })


def write_metadata(config,logger, table_name, dataframe):
    df_to_write = dataframe.copy(deep=True);
    dbType =  config['destination']['metadata']['dbType']
    index = config['destination']['metadata']['index']
    if 'RelativeFileArchiveURI' in df_to_write:
        destination =  config['destination']['files']['directory']
        for index, row in df_to_write.iterrows():
             if row.get("RelativeFileArchiveURI") is not None:
                print(row)
                destination_file = get_destination_location(row,destination)
                print('df',destination_file)
                if destination_file is not None:
                    df_to_write.at[index,'RelativeFileArchiveURI'] = destination_file

    if dbType == 'MSSQL':
        logger.debug({
            "message": f"Writing {df_to_write.shape[0]} records to {table_name}",
            "timestamp": datetime.datetime.now(datetime.UTC).timestamp() 
        })
        try:
            df_to_write.to_sql(table_name,config['destination']['metadata']['connectionString'],if_exists="append",index=False,index_label=index)
            logger.debug({
                "message": f"Finished writing {df_to_write.shape[0]} records to {table_name}",
                "timestamp": datetime.datetime.now(datetime.UTC).timestamp()
            })
        except Exception as e:
            logger.error({
                "message": e,
                "timestamp": datetime.datetime.now(datetime.UTC).timestamp()
            })
    else:
        logger.info({
            "message": f"{dbType} not implemented",
            "timestamp": datetime.datetime.now(datetime.UTC).timestamp() 
        })



def destination_writer(config, logger, table_name,dataframe):
    write_metadata(config,logger, table_name,dataframe)
    if 'RelativeFileArchiveURI' in dataframe:
        write_file(config, logger,dataframe)

