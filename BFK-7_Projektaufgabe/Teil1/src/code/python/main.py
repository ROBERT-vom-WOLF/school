from json import load as load_json
from Utils import Notifier, get_logger
from os import path, getcwd
from time import sleep


class App:
    def __init__(self, default: str = "111111"):
        self.active_value = default
        with open(path.join(path.dirname(path.dirname(getcwd())), "resources/config.json"), "r", encoding="utf-8") as file:
            self.config: dict[list | str, str | dict[str, str | int]] = load_json(file)

        log_file_path = path.join(path.dirname(path.dirname(path.dirname(getcwd()))), "appdata/logs/app.log")
        self.notifier = Notifier(
            self.config["SENDER_EMAIL_ADDRESS"],
            self.config["SENDER_EMAIL_PASSWD"],
            self.config["RECEIVER_EMAIL_ADDRESS"],
            log_file_path,
            port=587,
            server="smtp.gmail.com"
        )
        self.log = get_logger(App.__name__, log_file_path)
        self.triggered_water_areas = []

    def get_water_level(self, bit_value: str):
        """ Get the current water level by the bits from the water tank sensors. """
        if len(bit_value) != 6 or not all(x in "01" for x in bit_value):
            return None
        index = 0
        for bit in bit_value[::-1]:
            if bit != "1":
                break
            index += 1
        return self.config["WATER_LEVEL_NAMES"][::-1][index]

    @staticmethod
    def validate_bit_value(bit_value: str):
        """ Returns a bool, validating if a bit-string is usable and has no errors. """
        if len(bit_value) != 6 or not all(x in "01" for x in bit_value):
            return False

        if "1" in bit_value:
            if "0" in bit_value[bit_value.index("1")::]:
                return False

        return True

    def get_failing_sensor_name(self, bit_value: str):
        """ Get the name of the sensor that is failing by the bit-string of the sensors. """
        # no sensor signal of 1 is missing
        if "0" not in bit_value.strip("0"):
            return None

        return self.config["SENSOR_NAMES"][bit_value.rindex("0")]

    def mainloop(self):
        """ Mainloop of the app. """
        self.log.info("App starting up ...")
        water_level: str = self.get_water_level(self.active_value)

        while True:
            # sleep a shot time in case the logger flushes to late in the console
            sleep(0.1)

            # user input with a display wich displays the current value and water area
            user_input = input(f"({water_level}: {self.active_value}) | Sensor Value: ").lower().strip()

            if user_input == "exit":
                raise KeyboardInterrupt

            # a bool needed to detect if there were multiple bits or just one changed. when there a multiple changed,
            # it should not work due to the condition that the user cant put in a value that skips a sensor
            one_bit_changed = len([True for old_bit, new_bit in zip(self.active_value, user_input) if old_bit != new_bit]) <= 1

            # triggered when the bit-value is usable and is either smaller or higher by one than the current value
            if self.validate_bit_value(user_input) and (one_bit_changed or (one_bit_changed and int(user_input, 2) >= int(self.active_value, 2))):
                self.active_value = user_input
                water_level = self.get_water_level(self.active_value)

                # when the user enters a higher value (meaning the water was filled up)
                if int(user_input, 2) >= int(self.active_value, 2):
                    self.triggered_water_areas.clear()

                # when the notification for the area was not sent already, send an email
                if water_level not in self.triggered_water_areas:
                    self.notifier.send_email(message=f"Status:\n{self.config['NOTIFICATION_MESSAGES'][water_level]}")
                    self.triggered_water_areas.append(water_level)

                sleep(self.config["DELAYS"][water_level])

            # triggered when it is not a valid bit value (example 010111) but can be ordered to a water-level
            # this means a sensor is failing and not working properly
            elif not self.validate_bit_value(user_input) and self.get_water_level(user_input) is not None:
                self.log.warning(f"Sensor {self.get_failing_sensor_name(user_input)} is not working properly! Sensor send a value of '{user_input}'")
                self.notifier.send_email(
                    subject="Sensor not working properly!",
                    message=f"Sensor {self.get_failing_sensor_name(user_input)} is not working properly!\nSensor send a value of '{user_input}'"
                )
                sleep(self.config["DELAYS"]["PB0"])

            # when the change of the value is not allowed or the value has a wrong format
            else:
                self.log.error(f"Could not set value from '{self.active_value}' to '{user_input}'!")
                sleep(self.config["DELAYS"]["PB0"])


if __name__ == '__main__':
    app = App()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        app.log.info("App shutting down ...")
        exit(0)
