B) Logger Pi3 (Ubuntu): collector.service + simple_alerts.service
Prereqs on logger
1) Create directories + copy scripts
sudo mkdir -p /opt/labtools/logger /var/log/labtools
sudo cp collector.py simple_alerts.py /opt/labtools/logger/
sudo chmod +x /opt/labtools/logger/collector.py /opt/labtools/logger/simple_alerts.py

2) Create config file for collector

Put this at: /etc/labtools/collector_config.json

sudo mkdir -p /etc/labtools
sudo nano /etc/labtools/collector_config.json


Example contents (edit IP/user):

{
  "sources": [
    {
      "name": "smart_house_pi3",
      "host": "192.168.1.50",
      "port": 22,
      "user": "pi",
      "remote_path": "/var/log/labtools/iot_auth_events.jsonl"
    }
  ]
}

3) Create a dedicated user (recommended)
sudo useradd -r -s /usr/sbin/nologin -d /var/lib/labtools labtools 2>/dev/null || true
sudo mkdir -p /var/lib/labtools
sudo chown -R labtools:labtools /var/lib/labtools /var/log/labtools


Important: the labtools user must be able to SSH into the smart-house Pi3 (key-based).
You can put the private key in /var/lib/labtools/.ssh/ and lock perms:

sudo -u labtools mkdir -p /var/lib/labtools/.ssh
sudo -u labtools chmod 700 /var/lib/labtools/.ssh
# copy your key in as id_ed25519 (or generate one) then:
sudo chown -R labtools:labtools /var/lib/labtools/.ssh
sudo chmod 600 /var/lib/labtools/.ssh/id_*

B1) Logger: collector.service

Create: /etc/systemd/system/collector.service

[Unit]
Description=LabTools - SSH Log Collector (pull JSONL)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=labtools
Group=labtools
WorkingDirectory=/var/lib/labtools
ExecStart=/usr/bin/python3 /opt/labtools/logger/collector.py --config /etc/labtools/collector_config.json --outdir /var/log/labtools --interval 15
Restart=always
RestartSec=3

# Hardening (still allows ssh subprocess)
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/var/log/labtools /var/lib/labtools /etc/labtools
# If you store ssh keys in /var/lib/labtools/.ssh, allow it:
ReadWritePaths=/var/log/labtools /var/lib/labtools /etc/labtools

[Install]
WantedBy=multi-user.target

B2) Logger: simple_alerts.service

Create: /etc/systemd/system/simple_alerts.service

[Unit]
Description=LabTools - Simple Alerts (consume collected JSONL)
After=collector.service
Wants=collector.service

[Service]
Type=simple
User=labtools
Group=labtools
WorkingDirectory=/var/lib/labtools
ExecStart=/usr/bin/python3 /opt/labtools/logger/simple_alerts.py --in /var/log/labtools/smart_house_pi3.jsonl --out /var/log/labtools/alerts.jsonl --alert-sudo
Restart=always
RestartSec=3

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/var/log/labtools /var/lib/labtools

[Install]
WantedBy=multi-user.target

Enable + start on logger
sudo systemctl daemon-reload
sudo systemctl enable --now collector.service
sudo systemctl enable --now simple_alerts.service

sudo systemctl status collector.service --no-pager
sudo systemctl status simple_alerts.service --no-pager

Handy checks / troubleshooting
See logs
sudo journalctl -u auth_log_monitor.service -f
sudo journalctl -u collector.service -f
sudo journalctl -u simple_alerts.service -f

Confirm collector output files exist
ls -lah /var/log/labtools
tail -n 5 /var/log/labtools/collector_status.jsonl
tail -n 5 /var/log/labtools/smart_house_pi3.jsonl
tail -n 5 /var/log/labtools/alerts.jsonl

One critical note: remote path + permissions

Your collector config points at:
/var/log/labtools/iot_auth_events.jsonl on the smart-house box.

That’s good, because it avoids the SSH user needing access to /var/log/auth.log.
Just ensure the remote JSONL is readable by the SSH user (pi) or by whatever user you set in the config:

On smart-house Pi3:

sudo chmod 644 /var/log/labtools/iot_auth_events.jsonl