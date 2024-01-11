import asyncio
import os
import random
import time

import toml
from alert_feed import post_alert


def load_alerts():
    alerts_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alerts.toml")
    with open(alerts_path, "r") as file:
        data = toml.load(file)
    return data


def generate_random_alert(alerts):
    random_alert = random.choice([0, 1])
    print(alerts["alerts"][random_alert])
    return alerts["alerts"][random_alert]


async def main():
    alerts = load_alerts()

    alert = generate_random_alert(alerts)
    await post_alert(alert)


if __name__ == "__main__":
    asyncio.run(main())
