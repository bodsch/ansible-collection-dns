#

import datetime


def generate_serial(base_serial=None):
    """
    """
    today = datetime.datetime.utcnow().strftime("%Y%m%d")
    counter = 1
    serial = int(f"{today}{counter:02d}")

    # Optional: existing serial auslesen und erhöhen
    if base_serial and str(base_serial).startswith(today):
        old_counter = int(str(base_serial)[-2:])
        counter = old_counter + 1
        serial = int(f"{today}{counter:02d}")

    return serial
