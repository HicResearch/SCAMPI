import yaml
import datetime
import shutil
import os
import mysql
import sqlalchemy
def get_destination_location(row,destination):
    if('!' in row['RelativeFileArchiveURI']):
        return os.path.join(destination,row['RelativeFileArchiveURI'].split('!')[0].strip('/').split('/')[-1])
    return os.path.join(destination,row['RelativeFileArchiveURI'].strip('/').split('/')[-1])

def _source_relative_path(uri, sources):
    uri_path = os.path.abspath(uri)
    for source in sources.values():
        if source.get("type") != "filesystem" or not source.get("directory"):
            continue
        source_path = os.path.abspath(os.path.expanduser(source["directory"]))
        try:
            if os.path.commonpath([uri_path, source_path]) == source_path:
                return os.path.relpath(uri_path, source_path)
        except ValueError:
            continue
    return None

def write_file(config,logger,dataframe):
    start_time = datetime.datetime.now(datetime.UTC)
    files_config = config['destination']['files']
    destination = os.path.expanduser(files_config['directory'])
    os.makedirs(destination, exist_ok=True)

    if files_config.get('compress', False):
        logger.info({
            "message": f"Files were written to the compressed archive in {destination}",
            "timestamp": datetime.datetime.now(datetime.UTC).timestamp()
        })
        return

    redact_images = files_config.get("redact_images", False) is True
    if redact_images:
        from dicom_redactor import redact_archive_file, redact_dicom_file

    written_archives = []
    redactions_by_archive = {}
    if redact_images and "RelativeFileArchiveURI" in dataframe:
        dataframe["Redacted"] = False

    for row_index, row in dataframe.iterrows():
         RelativeFileArchiveURI = row.get("RelativeFileArchiveURI")
         if RelativeFileArchiveURI is not None:
            if '!' in RelativeFileArchiveURI: #archive
                source_archive, member = RelativeFileArchiveURI.split('!', 1)
                if source_archive not in written_archives:
                    destination_file = get_destination_location(row,destination).split('!')[0]
                    if destination_file is not None:
                        if redact_images:
                            redactions_by_archive[source_archive] = redact_archive_file(
                                source_archive, destination_file
                            )
                        else:
                            shutil.copyfile(source_archive,destination_file)
                        written_archives.append(source_archive)
                if redact_images:
                    dataframe.at[row_index, "Redacted"] = redactions_by_archive.get(
                        source_archive, {}
                    ).get(member.replace("\\", "/"), False)
            else:
                destination_file = get_destination_location(row,destination)
                if destination_file is not None:
                    if redact_images:
                        if RelativeFileArchiveURI.lower().endswith((".zip", ".7z")):
                            redactions = redact_archive_file(
                                RelativeFileArchiveURI, destination_file
                            )
                            dataframe.at[row_index, "Redacted"] = any(
                                redactions.values()
                            )
                        else:
                            dataframe.at[row_index, "Redacted"] = redact_dicom_file(
                                RelativeFileArchiveURI, destination_file
                            )
                    else:
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
                archive_path, member = uri.split('!',1)
                if metadata_directory:
                    relative_path = archive_path.replace(destination,metadata_directory)#os.path.relpath(archive_path, destination)
                    archive_path = os.path.join(
                        os.path.expanduser(metadata_directory), relative_path
                    )
                destination_file = f"{archive_path}!{member}"
            else:
                destination_file = os.path.join(
                    destination, "/".join(uri.strip('/').split("/")[1:])
                )
                if metadata_directory:
                    relative_path = _source_relative_path(
                        uri, config.get("sources", {})
                    )
                    if relative_path is None:
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
            if "Redacted" in df_to_write.columns:
                engine = sqlalchemy.create_engine(
                    config['destination']['metadata']['connectionString']
                )
                try:
                    _ensure_redacted_column(engine, table_name)
                finally:
                    engine.dispose()
            df_to_write.to_sql(table_name,config['destination']['metadata']['connectionString'],if_exists="append",index=False,index_label=index,
            dtype= { 'datefld': sqlalchemy.DateTime(), 
                    'intfld':  sqlalchemy.types.INTEGER(),
                    'strfld': sqlalchemy.types.NVARCHAR(length=255),
                    'floatfld': sqlalchemy.types.Float(precision=3, asdecimal=True),
                    'booleanfld': sqlalchemy.types.Boolean,
                    'Redacted': sqlalchemy.types.Boolean}
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


def _ensure_redacted_column(engine, table_name):
    inspector = sqlalchemy.inspect(engine)
    if not inspector.has_table(table_name):
        return
    columns = {
        column["name"].casefold()
        for column in inspector.get_columns(table_name)
    }
    if "redacted" in columns:
        return

    identifier_preparer = engine.dialect.identifier_preparer
    quoted_table = identifier_preparer.quote(table_name)
    quoted_column = identifier_preparer.quote("Redacted")
    statement = sqlalchemy.text(
        f"ALTER TABLE {quoted_table} ADD {quoted_column} BIT NOT NULL DEFAULT 0"
    )
    with engine.begin() as connection:
        connection.execute(statement)



def destination_writer(config, logger, table_name,dataframe):
    redact_images = (
        config.get("destination", {})
        .get("files", {})
        .get("redact_images", False) is True
    )
    if redact_images and 'RelativeFileArchiveURI' in dataframe:
        write_file(config, logger,dataframe)
    write_metadata(config,logger, table_name,dataframe)
    if not redact_images and 'RelativeFileArchiveURI' in dataframe:
        write_file(config, logger,dataframe)
