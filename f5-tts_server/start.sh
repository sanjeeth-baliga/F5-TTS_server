#!/bin/bash

# Start the FastAPI server with uvicorn
python -m uvicorn server:app --host 0.0.0.0 --port 7860

# Note: The --reload flag can be added during development for auto-reloading
# python -m uvicorn server:app --host 0.0.0.0 --port 7860 --reload
