# FrappeAPI

Better APIs for Frappe!

## Why?

The goal is to build a better API framework for Frappe.

FrappeAPI follows FastAPI's interface and semantics. For in-depth information about specific features, you can refer to [FastAPI's documentation](https://fastapi.tiangolo.com/).

## Latest Release - v0.2.0 🚀

The 0.2.0 release introduces **FastAPI-style path routing** - now you can define API endpoints using both traditional Frappe dotted paths and modern FastAPI-style path parameters:

```python
# Modern path-based routing with parameters in the URL
@app.get("/items/{item_id}")
def get_item(item_id: str):
    return {"item_id": item_id}
```

## Installation

```bash
pip install frappeapi
```
