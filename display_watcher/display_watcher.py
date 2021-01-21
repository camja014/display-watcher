import argparse
import logging
import os
import re
import subprocess
import time
from typing import Dict, Iterator, List, Optional, Set

DRM_PATH = "/sys/class/drm"

DRM_CARD_PATTERN = r"card[0-9]+$"

DRM_PORT_PATTERN = r"card[0-9]+.+"

LOG = logging.getLogger(name="display-watcher")


class Port:
    def __init__(self, path: str):
        self._path: str = path
        self._status: Optional[str] = None
        self._previous_status: Optional[str] = None
        self._changed = False

    def __str__(self):
        return self._path[len(DRM_PATH) + 1:]

    @property
    def connected(self) -> bool:
        return self._status == "connected"

    @property
    def path(self) -> str:
        return self._path

    @property
    def status(self) -> str:
        if self._status:
            return self._status
        else:
            return "none"

    @property
    def changed(self) -> bool:
        return self._changed

    def update(self):
        self._changed = False
        status_attr = os.path.join(self._path, "status")
        with open(status_attr) as f:
            status_str = f.readline().strip()
        self._previous_status = self._status
        self._status = status_str
        self._changed = self._status != self._previous_status
        LOG.debug("Port '%s' is %s. Was previously %s.", self, self._status,
                  self._previous_status)


class Card:
    def __init__(self, path: str):
        self._path = path
        self._ports: Dict[str, Port] = {}
        self._changed = False

    @property
    def path(self) -> str:
        return self._path

    @property
    def changed(self) -> bool:
        return self._changed

    def __str__(self):
        return self.path[len(DRM_PATH) + 1:]

    def _enum_ports(self) -> List[str]:
        # Scan all ports
        items = os.listdir(self._path)
        port_names = []
        for item in items:
            if re.match(DRM_PORT_PATTERN, item):
                LOG.debug("Found port '%s' in '%s'", item, self._path)
                port_names.append(item)
        return port_names

    def update(self):
        self._changed = False

        new_port_names_set = set(self._enum_ports())
        current_port_names_set = set(self._ports.keys())

        added_ports = new_port_names_set - current_port_names_set
        if added_ports:
            self._changed = True

        for name in added_ports:
            LOG.debug("Adding port '%s'", name)
            self._ports[name] = Port(os.path.join(self._path, name))

        removed_ports = current_port_names_set - new_port_names_set
        if removed_ports:
            self._changed = True

        for name in removed_ports:
            LOG.debug("Removing port '%s'", name)
            del self._ports[name]

        for port in self._ports.values():
            port.update()
            self._changed |= port.changed


def enum_cards() -> List[Card]:
    LOG.debug("Enumerating DRM devices in '%s'", DRM_PATH)
    items = os.listdir(DRM_PATH)
    card_paths = []

    for item in items:
        if re.match(DRM_CARD_PATTERN, item):
            card_path = os.path.join(DRM_PATH, item)
            LOG.info("Found DRM device '%s'", card_path)
            card_paths.append(card_path)

    return [Card(path) for path in card_paths]


def getargs():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p",
        "--polling-rate",
        default=0.2,
        type=float,
        help="Display status polling rate in Hz. Defaults to 0.2",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Verbosity level. Specify more than once to increase level.",
    )
    parser.add_argument(
        "cmd",
        nargs="+",
        help="Command to execute on state change.",
    )
    return parser.parse_args()


class Watcher:
    def __init__(self):
        self._cards = enum_cards()
        self._changed = False

    def poll(self):
        self._changed = False
        for card in self._cards:
            LOG.debug("Updating ports for card '%s'", card)
            card.update()
            self._changed |= card.changed

    def run(self):
        args = getargs()

        # Set logging level.
        if args.verbose >= 2:
            log_level = logging.DEBUG
        elif args.verbose == 1:
            log_level = logging.INFO
        else:
            log_level = logging.WARNING
        logging.basicConfig(format="[%(levelname)s] %(asctime)s: %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S",
                            level=log_level)

        self.poll()
        deadline = time.monotonic()
        while True:
            if time.monotonic() >= deadline:
                LOG.debug("Polling devices.")
                self.poll()
                if self._changed:
                    subprocess.run(args.cmd, check=False)
                deadline += args.polling_rate

            sleep_time = max(0, deadline - time.monotonic())
            time.sleep(sleep_time)


def main():
    try:
        watcher = Watcher()
        watcher.run()
    except KeyboardInterrupt:
        print("User requested termination.")


if __name__ == "__main__":
    main()
