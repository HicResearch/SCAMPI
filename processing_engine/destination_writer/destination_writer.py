import yaml
import datetime


def write_file():
    print('todo')

def write_metadata(config,logger, table_name, dataframe):
    dbType =  config['destination']['metadata']['dbType']
    index = config['destination']['metadata']['index']
    if dbType == 'MSSQL':
        logger.debug({
            "message": f"Writing {dataframe.shape[0]} records to {table_name}",
            "timestamp": datetime.datetime.now(datetime.UTC).timestamp() 
        })
        try:
            dataframe.to_sql(table_name,config['destination']['metadata']['connectionString'],if_exists="append",index=False,index_label=index)
            logger.debug({
                "message": f"Finished writing {dataframe.shape[0]} records to {table_name}",
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
    write_file()

