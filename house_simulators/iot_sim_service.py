"""
iot_sim_service.py (API + fake devices + state changes)

Lightweight HTTP server (Flask or stdlib)

Endpoints like:

POST /api/light/kitchen {on:true}

POST /api/thermostat {setpoint:21}

GET /api/state

Random “sensor telemetry” generator (temp, motion, door open)

Optional “bad choices” toggles (weak auth, default creds, verbose errors) so you can turn vuln modes on/off.
"""