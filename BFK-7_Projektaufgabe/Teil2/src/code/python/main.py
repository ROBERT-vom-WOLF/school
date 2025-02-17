from json import load as load_json
from Utils import Notifier, get_logger, DatabaseManager
from os import getcwd, path, listdir
from time import sleep


class App:
    def __init__(self, default: str = "111111", **kwargs):
        projekt_root_dir = path.dirname(path.dirname(path.dirname(getcwd())))
        config_path = path.join(projekt_root_dir, kwargs.get("config_location", "src/resources/config.json"))
        log_file_path = path.join(projekt_root_dir, kwargs.get("logfile_location", "appdata/app.log"))
        database_path = path.join(projekt_root_dir, kwargs.get("database_location", "appdata/messwerte.db"))

        assert "main.py" in listdir(getcwd()), "Programm can only be executed from the folder it lies in itself!"
        assert path.isfile(config_path), "No config-file found! Check out the README.md of this Project inside 'school/BFK-7_Projektaufgabe/README.md'"
        assert path.isfile(log_file_path), "No log-file found!"
        assert path.isfile(database_path), "No database-file found!"

        # load my config from my json file
        with open(config_path, "r", encoding="utf-8") as file:
            self.config: dict[list | str, str | dict[str, str | int]] = load_json(file)

        self.default_value = default
        self.active_value = default
        self.water_level = self.get_water_level(self.active_value)
        self.triggered_water_areas = []
        self.log = get_logger(self.__class__.__name__, log_file_path)
        self.database = DatabaseManager(database_path, log_file_path, kwargs.get("database_table", "messwerte"))
        self.notifier = Notifier(
            self.config["SENDER_EMAIL_ADDRESS"],
            self.config["SENDER_EMAIL_PASSWD"],
            self.config["RECEIVER_EMAIL_ADDRESS"],
            log_file_path,
            port=587,
            server="smtp.gmail.com"
        )

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

    def database_notification(self):
        total_wait_time = 0
        email_message = "Übersicht:"

        for entry in self.database.count_entries_by_level():
            level_name = entry[0]
            count = entry[1]
            if level_name in self.config["WATER_LEVEL_NAMES"]:
                wait_time = (self.config["DELAYS"][level_name]) / 60
                total_wait_time += wait_time
                email_message += f"\nAnzahl der Messwerte in {level_name}: {count:03d} --- {wait_time} min."
            elif level_name == "ERROR":
                email_message += f"\nAnzahl der Fehlermesswerte: {count:03d}"
            else:
                self.log.warning(f"Detected a entry wich can not be assigned ({count} times): {level_name}")

        email_message += f"\nGesamte Messzeit: {int(total_wait_time / 60)} h - {total_wait_time % 60} min"
        self.database.delete_all_entries()
        self.notifier.send_email(subject="Report", message=email_message)

    def handle_commands(self, commands: list[str]):
        """ Execute commands given in the commands list. Returns True when one was executed """
        command_executed = False
        for command in commands:
            if command == "help":
                print("##################################################################")
                print("## HELP MENU")
                print("## exit    - stop the programm")
                print("## clear   - clear the database")
                print("## notify  - send a notification about your database")
                print("## reset   - reset current user inputs to the default")
                print("## help    - show the help menu")
                print("##################################################################")
                command_executed = True

            if command == "exit":
                raise KeyboardInterrupt

            if command == "clear":
                command_executed = True
                self.database.delete_all_entries()

            if command == "notify":
                command_executed = True
                self.database_notification()

            if command == "reset":
                command_executed = True
                self.triggered_water_areas.clear()
                self.active_value = self.default_value
                self.water_level: str = self.get_water_level(self.active_value)

        return command_executed

    def mainloop(self):
        """ Mainloop of the app. """
        self.log.info("App starting up ...")
        while True:

            # sleep a shot time in case the logger flushes to late in the console
            sleep(0.1)

            # user input with a display wich displays the current value and water area
            user_input = input(f"({self.water_level}: {self.active_value}) | &> ").lower().strip()

            # handle defined commands:
            if self.handle_commands([x.strip() for x in user_input.split()]):
                continue

            # a bool needed to detect if there were multiple bits or just one changed. when there a multiple changed,
            # it should not work due to the condition that the user cant put in a value that skips a sensor
            one_bit_changed = len([True for old_bit, new_bit in zip(self.active_value, user_input) if old_bit != new_bit]) <= 1

            # triggered when the bit-value is usable and is either smaller or higher by one than the current value
            if self.validate_bit_value(user_input) and (one_bit_changed or (one_bit_changed and int(user_input, 2) >= int(self.active_value, 2))):
                self.active_value = user_input
                self.water_level = self.get_water_level(self.active_value)
                self.database.add_entry(self.water_level)

                # when the user enters a higher value (meaning the water was filled up)
                if int(user_input, 2) >= int(self.active_value, 2):
                    self.triggered_water_areas.clear()

                    # when the water level rises above a defined level, send a notification
                    if self.water_level in self.config["NOTIFICATION_WHEN_RISEN_ABOVE"]:
                        self.database_notification()

                # when the notification for the area was not sent already, send an email
                if self.water_level not in self.triggered_water_areas:
                    self.notifier.send_email(message=f"Status:\n{self.config['NOTIFICATION_MESSAGES'][self.water_level]}")
                    self.triggered_water_areas.append(self.water_level)

                sleep(self.config["DELAYS"][self.water_level])

            # triggered when it is not a valid bit value (example 010111) but can be ordered to a water-level
            # this means a sensor is failing and not working properly
            elif not self.validate_bit_value(user_input) and self.get_water_level(user_input) is not None:
                self.log.warning(f"Sensor {self.get_failing_sensor_name(user_input)} is not working properly! Sensor send a value of '{user_input}'")
                self.notifier.send_email(
                    subject="Sensor not working properly!",
                    message=f"Sensor {self.get_failing_sensor_name(user_input)} is not working properly!\nSensor send a value of '{user_input}'"
                )
                self.database.add_entry("ERROR")
                sleep(self.config["DELAYS"]["PB0"])

            # when the change of the value is not allowed or the value has a wrong format
            else:
                self.log.error(f"Could not set value from '{self.active_value}' to '{user_input}'!")
                self.database.add_entry("ERROR")
                sleep(self.config["DELAYS"]["PB0"])


if __name__ == '__main__':
    app = App()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        print("\n\r")
        app.log.info("App shutting down ...")
        exit(0)
