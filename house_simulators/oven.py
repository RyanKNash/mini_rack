"""
Simple oven simulation (thermostat-controlled).

- Thermostat with hysteresis controls the heating element
- Heat loss to room air continuously
- Heating element adds heat when ON
- Optional "door open" event adds extra heat loss

Runs minute-by-minute.
"""

from dataclasses import dataclass


@dataclass
class OvenThermostat:
    setpoint_c: float = 180.0
    deadband_c: float = 10.0          # ovens swing a lot, 5–20°C is common
    element_on: bool = False

    def update(self, temp_c: float) -> bool:
        low = self.setpoint_c - self.deadband_c / 2
        high = self.setpoint_c + self.deadband_c / 2

        if temp_c < low:
            self.element_on = True
        elif temp_c > high:
            self.element_on = False

        return self.element_on


@dataclass
class Oven:
    temp_c: float
    thermostat: OvenThermostat
    room_temp_c: float = 22.0

    # Tunable parameters (not physically exact; chosen for believable behavior)
    heat_power_c_per_min: float = 8.0      # heating rate when element is ON
    loss_rate_per_min: float = 0.03        # fraction of (temp-room) lost per minute

    # Door effects
    door_open: bool = False
    door_extra_loss_per_min: float = 0.12  # additional loss when door is open

    def step(self):
        """Advance simulation by 1 minute."""
        element = self.thermostat.update(self.temp_c)

        # base heat loss to room
        loss = self.loss_rate_per_min * (self.temp_c - self.room_temp_c)

        # door open increases loss a lot
        if self.door_open:
            loss += self.door_extra_loss_per_min * (self.temp_c - self.room_temp_c)

        # heating input
        heat_gain = self.heat_power_c_per_min if element else 0.0

        self.temp_c = self.temp_c + heat_gain - loss


def run_oven_sim(minutes: int = 90, log_every: int = 5):
    oven = Oven(
        temp_c=22.0,  # start at room temp
        thermostat=OvenThermostat(setpoint_c=180.0, deadband_c=10.0),
        room_temp_c=22.0,
        heat_power_c_per_min=8.0,
        loss_rate_per_min=0.03,
    )

    print("Oven simulation")
    print(f"Room: {oven.room_temp_c:.1f}°C | Setpoint: {oven.thermostat.setpoint_c:.1f}°C | Deadband: {oven.thermostat.deadband_c:.1f}°C")
    print("-" * 80)

    for t in range(1, minutes + 1):
        # Example door event: open at minute 45 for 3 minutes
        oven.door_open = (45 <= t < 48)

        oven.step()

        if t % log_every == 0 or t == 1 or t == minutes:
            h = t // 60
            m = t % 60
            state = "ON " if oven.thermostat.element_on else "OFF"
            door = "OPEN" if oven.door_open else "----"
            print(f"t={h:02d}:{m:02d}  Temp={oven.temp_c:6.1f}°C  Element={state}  Door={door}")

    print("-" * 80)
    print("Done.")


if __name__ == "__main__":
    run_oven_sim()
