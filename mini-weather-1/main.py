from machine import ADC, Pin
import dht
import utime


class EnvironmentMonitor:
    def __init__(self, dht_pin, soil_adc, soil_pwr):
        # Initialize Sensors
        self.dht = dht.DHT11(Pin(dht_pin))
        self.soil = ADC(Pin(soil_adc))

        # Power pin for soil sensor to prevent corrosion
        self.soil_pwr = Pin(soil_pwr, Pin.OUT)
        self.soil_pwr.value(0)

    def read_soil(self):
        """Activates sensor, takes reading, deactivates."""
        self.soil_pwr.value(1)
        utime.sleep_ms(10)  # Capacitive settling time

        # Take two readings, discard first to clear ADC mux ghosting
        self.soil.read_u16()
        val = self.soil.read_u16()

        self.soil_pwr.value(0)
        return val

    def get_data(self):
        """Aggregates data from all sources."""
        data = {
            "temp": None,
            "hum": None,
            "soil": self.read_soil(),
        }

        try:
            self.dht.measure()
            data["temp"] = self.dht.temperature()
            data["hum"] = self.dht.humidity()
        except OSError:
            # DHT11 often fails if polled too fast or during voltage dips
            pass

        return data


def main():
    # Pin Configuration
    monitor = EnvironmentMonitor(dht_pin=16, soil_adc=27, soil_pwr=22)

    print("System Initialised. Starting telemetry...")

    while True:
        start_time = utime.ticks_ms()

        results = monitor.get_data()

        # Pythonic string formatting
        output = ("Temp: {temp}°C | Hum: {hum}% |  Soil: {soil:5d}").format(**results)

        print(output)

        # Maintain a 1-second cadence regardless of processing time
        elapsed = utime.ticks_diff(utime.ticks_ms(), start_time)
        utime.sleep_ms(max(0, 1000 - elapsed))


try:
    main()
except KeyboardInterrupt:
    print("\nMonitoring stopped by user.")
