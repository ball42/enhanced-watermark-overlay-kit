"""
EWOK - Enhanced Watermark Overlay Kit
Main application entry point: `ewok` (or `python app.py`) serves on
127.0.0.1 only. EWOK is a local tool with no authentication.
"""

import argparse

import config
from app_factory import create_app

app = create_app()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ewok", description=__doc__)
    parser.add_argument("--port", type=int, default=config.PORT)
    args = parser.parse_args(argv)
    print(f"EWOK on http://{config.HOST}:{args.port}")
    app.run(host=config.HOST, port=args.port, debug=config.DEBUG)


if __name__ == "__main__":
    main()
