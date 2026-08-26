import yaml

config = None


def write_file():
    print('todo')

def write_metadata(config,table_name, dataframe):
    dbType =  config['destination']['metadata']['dbType']
    index = config['destination']['metadata']['index']
    if dbType == 'MSSQL':
        print(table_name,dataframe.shape)
        dataframe.to_sql(table_name,config['destination']['metadata']['connectionString'],if_exists="append",index=False,index_label=index)
    else:
        print(config['destination']['metadata']['dbType'], " not implemented")



def destination_writer(table_name,dataframe):
    with open("/config.yml") as ymlstream:
        try:
            config  = yaml.safe_load(ymlstream)
        except yaml.YAMLError as exc:
            raise RuntimeError(exc)

    write_metadata(config,table_name,dataframe)

