# DICOM Task Analytics

This Grafana platform is for monitoring DICOM processing tasks over time. Promtail collects logs from the processing engine, Loki stores and indexes them, and Grafana provides dashboards and log exploration.

## Quickstart

### 1. Start the sample stack

Run these commands from `analytics_platform`:

```shell
docker compose up -d
```

This starts Grafana, Loki, and Promtail. The Grafana UI is available at [http://localhost:3000](http://localhost:3000). On a fresh Grafana installation, sign in with `admin` / `admin` and follow the prompt to set a new password.

The sample `docker-compose.yaml` includes host-specific Windows volume paths. Before starting the stack on another machine, update those paths to match your local checkout. Promtail is configured to read logs from `processing_engine/logs`.

To stop the stack, run:

```shell
docker compose down
```

### 2. Add Loki as a data source

In Grafana, open **Connections → Data sources → Add data source**, select **Loki**, and set the URL to:

```text
http://loki:3100
```

Use the Docker service name `loki` here (not `localhost`), since Grafana connects to Loki over the Compose network. Save and test the data source.

### 3. Import the dashboards

In Grafana, go to **Dashboards → New → Import** and upload the JSON dashboard files from the [`dashboards`](dashboards/) directory. Select the Loki data source if Grafana asks you to map a data source, then import the dashboard.

