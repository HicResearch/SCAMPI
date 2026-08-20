from source_extractor import source_extractor
from metadata_processor import metadata_processor

def run():
    source_extractor.source_extractor()
    metadata_processor.metadata_processor()

if(__name__ == "__main__"):
    run()