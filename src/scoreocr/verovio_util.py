from importlib.resources import files

import verovio

# verovio.setDefaultResourcePath() (called at import time in verovio/__init__.py)
# only takes effect for toolkits constructed on the same thread that ran the
# import. A toolkit constructed on any other thread (e.g. the batch runner's
# background worker thread, or a FastAPI threadpool worker serving a sync
# route) silently falls back to a hardcoded system path and fails to load its
# fonts. Set the resource path explicitly on every toolkit so Verovio use is
# thread-safe regardless of where the toolkit is constructed.
_RESOURCE_PATH = str(files("verovio") / "data")


def new_toolkit():
    tk = verovio.toolkit()
    tk.setResourcePath(_RESOURCE_PATH)
    return tk
