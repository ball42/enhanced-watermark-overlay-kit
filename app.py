"""
EWOK - Enhanced Watermark Overlay Kit
Main application entry point: `ewok` (or `python app.py`) serves on
127.0.0.1 only. EWOK is a local tool with no authentication.
"""

import argparse
import os
import threading
import webbrowser

import config
from app_factory import create_app

app = create_app()


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ewok",
        description="Run EWOK, the local watermark editor and Brander template designer.")
    parser.add_argument("--port", type=int, default=config.PORT,
                        help="Port to serve on (default 5055, or EWOK_PORT).")
    parser.add_argument("--open", action="store_true",
                        help="Open the template designer in the default browser.")
    args = parser.parse_args(argv)
    url = f"http://{config.HOST}:{args.port}"
    print(f"EWOK on {url}  (Template designer: /template)")
    # With the debug reloader, the child process sets WERKZEUG_RUN_MAIN:
    # only the first process opens the browser.
    if args.open and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        threading.Timer(1.0, webbrowser.open, args=(f"{url}/template",)).start()
    app.run(host=config.HOST, port=args.port, debug=config.DEBUG)


if __name__ == "__main__":
    main()
