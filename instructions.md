smart house pi3:
    sudo python3 auth_log_monitor.py --out /var/log/iot_auth_events.jsonl --print

logger pi3:
    python3 simple_alerts.py --in ./iot_auth_events.jsonl --out ./alerts.jsonl --alert-sudo
