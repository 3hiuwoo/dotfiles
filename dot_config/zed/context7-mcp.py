"""Launch Context7 with a machine-local API key, outside tracked settings."""

import json
import os
from pathlib import Path
import sys


def main():
    credentials = Path.home() / ".config/zed/chezmoi-local.json"
    env = os.environ.copy()
    if credentials.exists():
        try:
            key = json.loads(credentials.read_text()).get("context7_api_key", "")
            if not isinstance(key, str):
                raise ValueError
        except (OSError, ValueError, AttributeError):
            sys.exit("Context7: cannot read API key from ~/.config/zed/chezmoi-local.json")
        if key:
            env["CONTEXT7_API_KEY"] = key

    # Match the installed extension's version; keep the key out of arguments.
    os.execvpe("npx", ["npx", "--yes", "@upstash/context7-mcp@4.4.4", *sys.argv[1:]], env)


if __name__ == "__main__":
    main()
