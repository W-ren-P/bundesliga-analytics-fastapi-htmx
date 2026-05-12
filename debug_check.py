from fastapi.templating import Jinja2Templates
from fastapi import Request
from starlette.datastructures import URL

templates = Jinja2Templates(directory="templates")

class MockRequest:
    def __init__(self):
        self.scope = {
            "type": "http",
            "server": ("127.0.0.1", 8000),
            "path": "/",
            "headers": [],
            "app": None
        }
    def url_for(self, name, **path_params):
        return f"/{name}/{path_params.get('path', '')}"

try:
    # This is a bit complex to mock correctly for url_for to work in Starlette
    # Let's just try to render without mocking too much and see if it fails on something obvious
    print("Attempting to render index.html...")
    # Starlette's TemplateResponse needs a real request object or at least something that looks like it
    # We'll just check if the files exist first.
    import os
    for f in ["templates/index.html", "templates/base.html"]:
        if os.path.exists(f):
            print(f"{f} exists")
        else:
            print(f"{f} MISSING")
            
except Exception as e:
    print(f"Error: {e}")
