smart house pi3:
    sudo python3 auth_log_monitor.py --out /var/log/iot_auth_events.jsonl --print

logger pi3:
    python3 simple_alerts.py --in ./iot_auth_events.jsonl --out ./alerts.jsonl --alert-sudo
    rsync -az --append-verify pi@SMART_HOUSE_IP:/var/log/iot_auth_events.jsonl ~/telemetry/iot_auth_events.jsonl