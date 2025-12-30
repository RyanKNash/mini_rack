"""
Basic thermostat simulation for a multi-room house.

- Each room has its own thermostat (setpoint + deadband).
- When temp < setpoint - deadband/2 => heat turns ON
- When temp > setpoint + deadband/2 => heat turns OFF
- Temperature changes based on:
    * heat input (when ON)
    * heat loss to outside (always)
    * mild air mixing with other rooms

This is intentionally simplified but behaves realistically (no rapid toggling).
"""

from dataclasses import dataclass
from typing import List


@dataclass
class Thermostat:
    setpoint_c: float = 21.0          # desired temperature
    deadband_c: float = 0.8           # hysteresis band to avoid rapid cycling
    heat_on: bool = False

    def update(self, temp_c: float) -> bool:
        """Update heat_on based on current temperature and hysteresis."""
        low = self.setpoint_c - self.deadband_c / 2
        high = self.setpoint_c + self.deadband_c / 2

        if temp_c < low:
            self.heat_on = True
        elif temp_c > high:
            self.heat_on = False

        return self.heat_on


@dataclass
class Room:
    name: str
    temp_c: float
    thermostat: Thermostat
    heat_power_c_per_min: float = 0.08   # how fast this room heats when ON
    loss_rate_per_min: float = 0.01      # fraction of difference to outside lost per minute


class House:
    def __init__(self, rooms: List[Room], outside_temp_c: float = 5.0, mix_rate_per_min: float = 0.02):
        self.rooms = rooms
        self.outside_temp_c = outside_temp_c
        self.mix_rate_per_min = mix_rate_per_min  # air mixing between rooms per minute

    def step(self):
        """Advance the simulation by 1 minute."""
        # 1) thermostat decisions
        heat_flags = []
        for r in self.rooms:
            heat_flags.append(r.thermostat.update(r.temp_c))

        # 2) compute mixing target (average temp)
        avg_temp = sum(r.temp_c for r in self.rooms) / len(self.rooms)

        # 3) update each room temp
        for r, heat_on in zip(self.rooms, heat_flags):
            # heat input
            heat_gain = r.heat_power_c_per_min if heat_on else 0.0

            # heat loss proportional to difference from outside
            loss = r.loss_rate_per_min * (r.temp_c - self.outside_temp_c)

            # mixing pulls room a bit toward house average
            mixing = self.mix_rate_per_min * (avg_temp - r.temp_c)

            r.temp_c = r.temp_c + heat_gain - loss + mixing

    def snapshot(self) -> str:
        """Human-readable state of the house."""
        parts = []
        for r in self.rooms:
            parts.append(f"{r.name}: {r.temp_c:5.2f}°C  {'HEAT' if r.thermostat.heat_on else '----'}  "
                         f"(set {r.thermostat.setpoint_c:.1f})")
        return " | ".join(parts)


def run_sim(minutes: int = 6 * 60, log_every: int = 30):
    # Example house: 3 rooms with slightly different setpoints
    rooms = [
        Room("Living", temp_c=18.0, thermostat=Thermostat(setpoint_c=21.0, deadband_c=0.8),
             heat_power_c_per_min=0.10, loss_rate_per_min=0.010),
        Room("Bedroom", temp_c=17.0, thermostat=Thermostat(setpoint_c=20.0, deadband_c=0.8),
             heat_power_c_per_min=0.07, loss_rate_per_min=0.012),
        Room("Office", temp_c=16.5, thermostat=Thermostat(setpoint_c=22.0, deadband_c=0.8),
             heat_power_c_per_min=0.09, loss_rate_per_min=0.011),
    ]

    house = House(rooms, outside_temp_c=5.0, mix_rate_per_min=0.02)

    print("Starting simulation")
    print(f"Outside: {house.outside_temp_c:.1f}°C")
    print(house.snapshot())
    print("-" * 120)

    for t in range(1, minutes + 1):
        house.step()

        if log_every and (t % log_every == 0 or t == 1 or t == minutes):
            hr = t // 60
            mn = t % 60
            print(f"t={hr:02d}:{mn:02d}  {house.snapshot()}")

    print("-" * 120)
    print("Done.")


if __name__ == "__main__":
    # 6 hours, print every 30 minutes
    run_sim(minutes=6 * 60, log_every=30)
