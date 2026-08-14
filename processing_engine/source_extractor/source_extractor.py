import yaml

config = None

with open("/SCAMPI/config.yml") as ymlstream:
    try:
        config  = yaml.safe_load(ymlstream)
    except yaml.YAMLError as exc:
        print(exc)

print(config)
