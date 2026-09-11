from unittest.mock import Mock
import pandas as pd


from destination_writer.destination_writer import destination_writer

def test_write_metadata_bad_connection():
    logger = Mock()
    config = {
        "destination":{
            "metadata":{
                "dbType":"MSSQL",
                "connectionString":"",
                "index":"test"
            }
        }
    }
    table_name="test_write_metadata"
    dataframe = pd.DataFrame()
    dataframe.insert(0,"test",[1])
    destination_writer(config,logger,table_name,dataframe)
    logger.debug.assert_called_once()
    assert logger.debug.call_args.args[0]["message"] == f"Writing 1 records to {table_name}"
    logger.error.assert_called_once()


def test_write_metadata_db_not_implemented():
    logger = Mock()
    config = {
        "destination":{
            "metadata":{
                "dbType":"Junk",
                "connectionString":"",
                "index":"test"
            }
        }
    }
    table_name="test_write_metadata"
    dataframe = pd.DataFrame()
    dataframe.insert(0,"test",[1])
    destination_writer(config,logger,table_name,dataframe)
    logger.debug.assert_not_called()
    logger.info.assert_called_once()
    assert logger.info.call_args.args[0]["message"] == f"Junk not implemented"
