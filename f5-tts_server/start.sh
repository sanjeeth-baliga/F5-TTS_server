#!/bin/bash

# Start the Gradio server with specified port and host
f5-tts_infer-gradio --port 7860 --host 0.0.0.0

# Note: The --share option is commented out by default since it's typically not needed when running in Docker
# Uncomment the following line if you want to enable share link:
# f5-tts_infer-gradio --share
