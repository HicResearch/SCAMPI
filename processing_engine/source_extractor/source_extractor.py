import yaml

config = None

with open("/mnt/config.yml") as ymlstream:
    try:
        config  = yaml.safe_load(ymlstream)
    except yaml.YAMLError as exc:
        print(exc)

print(config)
