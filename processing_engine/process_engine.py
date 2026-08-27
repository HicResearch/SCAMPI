from source_extractor import source_extractor
from metadata_processor import metadata_processor
import logging
import yaml
import datetime
from pythonjsonlogger.json import JsonFormatter


def run():

    logger = logging.getLogger()
    logging.basicConfig(filename=f'/SCAMPI/logs/{datetime.datetime.utcnow()}.log', encoding='utf-8', level=logging.DEBUG)##TODO put this log somewhere sensible
    logHandler = logging.StreamHandler()
    formatter = JsonFormatter()
    logHandler.setFormatter(formatter)
    logger.addHandler(logHandler)

    config = None
    with open("/config.yml") as ymlstream:
        try:
            config  = yaml.safe_load(ymlstream)
        except yaml.YAMLError as exc:
            logger.error({
                "message":exc,
                "timestamp": datetime.datetime.utcnow()
            })
            raise RuntimeError(exc)

    source_extractor.source_extractor(config, logger)
    metadata_processor.metadata_processor(config, logger)

if(__name__ == "__main__"):
    run()