# F5-TTS Server

F5-TTS Server is a FastAPI application that provides endpoints for text-to-speech conversion and voice cloning. It offers a simple and efficient way to generate natural-sounding speech from text using various voices and accents.

This project is built on top of [F5-TTS](https://github.com/SWivid/F5-TTS), a text-to-speech system that enables high-quality voice synthesis and cloning.

## Features

- Text-to-speech conversion with customizable voices
- Voice cloning capabilities
- Adjustable speech speed
- Audio file upload and processing

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/ValyrianTech/F5-TTS_server.git
   ```
2. Navigate to the project directory:
   ```bash
   cd F5-TTS_server
   ```
3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

To start the server, run:

```bash
uvicorn f5-tts_server.server:app --host 0.0.0.0 --port 8000
```

The server provides the following endpoints:

### 1. Base Text-to-Speech

Performs text-to-speech conversion using the base speaker.

**Endpoint:** `/base_tts/`

**Method:** `GET`

**Parameters:**
- `text` (str): The text to convert to speech
- `accent` (str, optional): The accent to use. Default: 'en-newest'
- `speed` (float, optional): Speech speed. Default: 1.0

### 2. Voice Change

Changes the voice of an existing audio file.

**Endpoint:** `/change_voice/`

**Method:** `POST`

**Parameters:**
- `reference_speaker` (str): The reference speaker name
- `file` (file): Audio file to process

### 3. Upload Audio

Upload a reference audio file for voice cloning.

**Endpoint:** `/upload_audio/`

**Method:** `POST`

**Parameters:**
- `audio_file_label` (str): Label for the uploaded audio
- `file` (file): Audio file to upload

### 4. Synthesize Speech

Synthesize speech using a specific voice and style.

**Endpoint:** `/synthesize_speech/`

**Method:** `GET`

**Parameters:**
- `text` (str): Text to synthesize
- `voice` (str): Voice to use
- `accent` (str, optional): Accent to use. Default: 'en-newest'
- `speed` (float, optional): Speech speed. Default: 1.0

## Response Headers

All synthesis endpoints include these response headers:
- `x-elapsed-time`: Time taken for synthesis (seconds)
- `x-device-used`: Device used for synthesis (CPU/GPU)

## Example Usage

```python
import requests

# Basic text-to-speech
url = "http://localhost:8000/base_tts/"
params = {
    "text": "Hello, this is a test.",
    "accent": "en-newest",
    "speed": 1.0
}

response = requests.get(url, params=params)
with open("output.wav", "wb") as f:
    f.write(response.content)

# Voice cloning
url = "http://localhost:8000/synthesize_speech/"
params = {
    "text": "Hello, this is a test.",
    "voice": "custom_voice",
    "accent": "en-newest",
    "speed": 1.0
}

response = requests.get(url, params=params)
with open("cloned_voice.wav", "wb") as f:
    f.write(response.content)
