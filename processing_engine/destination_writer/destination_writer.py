import yaml
import datetime
import shutil
import os
import mysql
import sqlalchemy
def get_destination_location(row,destination):
    if('!' in row['RelativeFileArchiveURI']):
        return os.path.join(destination,row['RelativeFileArchiveURI'].split('!')[0].split('/')[-1])
    return os.path.join(destination,row['RelativeFileArchiveURI'].split('/')[-1])

def write_file(config,logger,dataframe):
    start_time = datetime.datetime.now(datetime.UTC)
    destination = os.path.expanduser(config['destination']['files']['directory'])
    os.makedirs(destination, exist_ok=True)

    if config['destination']['files'].get('compress', False):
        logger.info({
            "message": f"Files were written to the compressed archive in {destination}",
            "timestamp": datetime.datetime.now(datetime.UTC).timestamp()
        })
        return

    written_archives = []

    for _, row in dataframe.iterrows():
         RelativeFileArchiveURI = row.get("RelativeFileArchiveURI")
         if RelativeFileArchiveURI is not None:
            if '!' in RelativeFileArchiveURI: #archive
                if(RelativeFileArchiveURI.split('!')[0] in written_archives):
                    continue
                else:
                    destination_file = get_destination_location(row,destination).split('!')[0]
                    if destination_file is not None:
                        shutil.copyfile(RelativeFileArchiveURI.split('!')[0],destination_file)
                        written_archives.append(RelativeFileArchiveURI.split('!')[0])
            else:
                destination_file = get_destination_location(row,destination)
                if destination_file is not None:
                    shutil.copyfile(RelativeFileArchiveURI,destination_file)
    end_time = datetime.datetime.now(datetime.UTC)
    logger.info({
        "message":f"Wrote {len(dataframe.index)} files in {(end_time-start_time).total_seconds()} seconds",
        "timestamp": datetime.datetime.now(datetime.UTC).timestamp()
    })


def write_metadata(config,logger, table_name, dataframe):
    df_to_write = dataframe.copy(deep=True);
    dbType =  config['destination']['metadata']['dbType']
    index = config['destination']['metadata']['index']
    files_config = config.get('destination', {}).get('files', {})
    compress = files_config.get('compress', False)
    metadata_directory = files_config.get('metadata_directory')
    if 'RelativeFileArchiveURI' in df_to_write:
        destination = os.path.expanduser(files_config['directory'])
        for index, row in df_to_write.iterrows():
            uri = row.get("RelativeFileArchiveURI")
            if uri is None:
                continue
            if compress:
                archive_path, member = uri.split("!", 1)
                if metadata_directory:
                    relative_path = os.path.relpath(archive_path, destination)
                    archive_path = os.path.join(
                        os.path.expanduser(metadata_directory), relative_path
                    )
                destination_file = f"{archive_path}!{member}"
            else:
                destination_file = os.path.join(
                    destination, "/".join(uri.split("/")[1:])
                )
                if metadata_directory:
                    relative_path = os.path.relpath(destination_file, destination)
                    destination_file = os.path.join(
                        os.path.expanduser(metadata_directory), relative_path
                    )

            df_to_write.at[index, "RelativeFileArchiveURI"] = destination_file.replace("\\", "/")

    if dbType == 'MSSQL':
        logger.debug({
            "message": f"Writing {df_to_write.shape[0]} records to {table_name}",
            "timestamp": datetime.datetime.now(datetime.UTC).timestamp() 
        })
        try:
            df_to_write.to_sql(table_name,config['destination']['metadata']['connectionString'],if_exists="append",index=False,index_label=index,
            dtype= { 'datefld': sqlalchemy.DateTime(), 
                    'intfld':  sqlalchemy.types.INTEGER(),
                    'strfld': sqlalchemy.types.NVARCHAR(length=255),
                    'floatfld': sqlalchemy.types.Float(precision=3, asdecimal=True),
                    'booleanfld': sqlalchemy.types.Boolean}                   
            )
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
