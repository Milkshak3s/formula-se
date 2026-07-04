"""Entrypoint: ``python -m fse_agent -c config.toml`` (or the ``fse-agent`` script)."""
from __future__ import annotations

import argparse
import logging
import sys

from .agent import Agent
from .client import ApiClient
from .config import Config, ConfigError
from .se_control import make_controller


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="fse-agent", description="Formula SE dedicated-server agent"
    )
    parser.add_argument("-c", "--config", default="config.toml", help="path to config.toml")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        config = Config.load(args.config)
        config.validate_for_run()
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    client = ApiClient(config.api_base_url, config.token, verify_tls=config.verify_tls)
    controller = make_controller(config)
    agent = Agent(config, client, controller)
    try:
        agent.run()
    except KeyboardInterrupt:
        print("stopped", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
