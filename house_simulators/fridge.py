"""
Simple refrigerator simulation.

- Thermostat with hysteresis controls compressor
- Heat leaks in from room air
- Compressor removes heat when ON
- Temperature updated once per minute
"""

from dataclasses import dataclass


@dataclass
class FridgeThermostat:
    setpoint_c: float = 4.0        # target fridge temp (typical 3–5°C)
    deadband_c: float = 1.5        # hysteresis to prevent rapid cycling
    compressor_on: bool = False

    def update(self, temp_c: float) -> bool:
        high = self.setpoint_c + self.deadband_c / 2
        low = self.setpoint_c - self.deadband_c / 2

        if temp_c > high:
            self.compressor_on = True
        elif temp_c < low:
            self.compressor_on = False

        return self.compressor_on


@dataclass
class Fridge:
    temp_c: float
    thermostat: FridgeThermostat
    room_temp_c: float = 22.0

    # physics-ish parameters (tuned for realism, not accuracy)
    cooling_rate_c_per_min: float = 0.25   # how fast compressor cools
    heat_leak_rate_per_min: float = 0.02   # how fast heat leaks in

    def step(self):
        """Advance simulation by 1 minute."""
        compressor = self.thermostat.update(self.temp_c)

        # heat leak from room
        heat_gain = self.heat_leak_rate_per_min * (self.room_temp_c - self.temp_c)

        # cooling from compressor
        cooling = self.cooling_rate_c_per_min if compressor else 0.0

        self.temp_c = self.temp_c + heat_gain - cooling


def run_fridge_sim(minutes: int = 6 * 60, log_every: int = 10):
    fridge = Fridge(
        temp_c=8.0,  # warm start
        thermostat=FridgeThermostat(setpoint_c=4.0, deadband_c=1.5),
        room_temp_c=22.0,
    )

    print("Refrigerator simulation")
    print(f"Room temp: {fridge.room_temp_c:.1f}°C")
    print("-" * 60)

    for t in range(1, minutes + 1):
        fridge.step()

        if t % log_every == 0 or t == 1 or t == minutes:
            h = t // 60
            m = t % 60
            state = "ON " if fridge.thermostat.compressor_on else "OFF"
            print(f"t={h:02d}:{m:02d}  Temp={fridge.temp_c:5.2f}°C  Compressor={state}")

    print("-" * 60)
    print("Done.")


if __name__ == "__main__":
    # 6 hours, log every 10 minutes
    run_fridge_sim()
