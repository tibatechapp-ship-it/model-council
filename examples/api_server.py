"""Serve the deliberation API programmatically.

Run:  python examples/api_server.py
Then: curl -s localhost:8000/v1/deliberations -X POST \
        -H 'content-type: application/json' \
        -d '{"question":"Should we ship on Friday?","rounds":1}'
"""

import uvicorn

from model_council.api.app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
