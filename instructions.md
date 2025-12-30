How to run it

On logger Pi3, make sure SSH key access works:

ssh pi@192.168.1.50 "echo ok"


Start collector:

python3 collector.py --config ./collector_config.json --outdir ~/telemetry --interval 15


You’ll get:

~/telemetry/smart_house_pi3.jsonl (the collected events)

~/telemetry/collector_offsets.json (byte offsets per source)

~/telemetry/collector_status.jsonl (health + fetch logs)


smart house pi3:
    sudo python3 auth_log_monitor.py --out /var/log/iot_auth_events.jsonl --print

logger pi3:
    python3 simple_alerts.py --in ./iot_auth_events.jsonl --out ./alerts.jsonl --alert-sudo
    rsync -az --append-verify pi@SMART_HOUSE_IP:/var/log/iot_auth_events.jsonl ~/telemetry/iot_auth_events.jsonl
    python3 simple_alerts.py --in ~/telemetry/smart_house_pi3.jsonl --out ~/telemetry/alerts.jsonl --alert-sudo
