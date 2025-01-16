import os
import time
import torch
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse
from typing import Optional
from pydantic import BaseModel
import logging
import io
import magic
from f5_tts.api import F5TTS
import soundfile as sf
from pydub import AudioSegment
import re
from importlib.resources import files
from cached_path import cached_path

logging.basicConfig(level=logging.INFO)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

device = "cuda:0" if torch.cuda.is_available() else "cpu"

# Initialize F5-TTS model with English settings
model = F5TTS(
    device=device,
    model_type="F5-TTS",
    vocab_file="byte",  # Use byte tokenizer for English text
    ode_method="euler",
    use_ema=True,
    vocoder_name="vocos",
    ckpt_file=str(cached_path("hf://SWivid/F5-TTS/F5TTS_Base/model_1200000.safetensors"))  # Use the base model
)

output_dir = 'outputs'
os.makedirs(output_dir, exist_ok=True)

# Copy the English reference audio to resources if it doesn't exist
resources_dir = 'resources'
os.makedirs(resources_dir, exist_ok=True)
default_ref_audio = str(files("f5_tts").joinpath("infer/examples/basic/basic_ref_en.wav"))
default_ref_text = "Some call me nature, others call me mother nature."

if not os.path.exists(f"{resources_dir}/default_en.wav"):
    import shutil
    shutil.copy2(default_ref_audio, f"{resources_dir}/default_en.wav")

os.makedirs("resources", exist_ok=True)

def convert_to_wav(input_path, output_path):
    """Convert any audio format to WAV using pydub."""
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_frame_rate(22050)  # F5-TTS expects 22050Hz
    audio = audio.set_channels(1)  # Convert to mono
    audio.export(output_path, format='wav')

def split_text_into_sentences(text):
    """Split text into sentences using regex."""
    # Split on common sentence endings
    sentences = re.split(r'(?<=[.!?])\s+', text)
    # Remove empty sentences and extra whitespace
    sentences = [s.strip() for s in sentences if s.strip()]
    return sentences

class UploadAudioRequest(BaseModel):
    audio_file_label: str

@app.on_event("startup")
async def startup_event():
    test_text = "This is a test sentence generated by the F5-TTS API."
    voice = "demo_speaker0"
    await synthesize_speech(test_text, voice)

@app.get("/base_tts/")
async def base_tts(text: str, accent: Optional[str] = 'en-newest', speed: Optional[float] = 1.0):
    """
    Perform text-to-speech conversion using only the base speaker.
    """
    try:
        # Use the default English voice
        return await synthesize_speech(text=text, voice="default_en", accent=accent, speed=speed)
    except Exception as e:
        logging.error(f"Error in base_tts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/change_voice/")
async def change_voice(reference_speaker: str = Form(...), file: UploadFile = File(...), watermark: Optional[str] = "@F5-TTS"):
    """
    Change the voice of an existing audio file.
    """
    try:
        logging.info(f'changing voice to {reference_speaker}...')

        contents = await file.read()
        
        # Save the input audio temporarily
        input_path = f'{output_dir}/input_audio.wav'
        with open(input_path, 'wb') as f:
            f.write(contents)

        # Find the reference audio file
        matching_files = [file for file in os.listdir("resources") if file.startswith(str(reference_speaker))]
        if not matching_files:
            raise HTTPException(status_code=400, detail="No matching reference speaker found.")
        
        reference_file = f'resources/{matching_files[0]}'
        
        # Convert reference file to WAV if it's not already
        if not reference_file.lower().endswith('.wav'):
            ref_wav_path = f'{output_dir}/ref_converted.wav'
            convert_to_wav(reference_file, ref_wav_path)
            reference_file = ref_wav_path
        
        # For voice conversion, we'll use the same text for both reference and generation
        # This helps maintain the timing and prosody
        text = model.transcribe(input_path)
        save_path = f'{output_dir}/output_converted.wav'

        wav, sr, _ = model.infer(
            ref_file=reference_file,
            ref_text=text,
            gen_text=text,
            file_wave=save_path
        )

        result = StreamingResponse(open(save_path, 'rb'), media_type="audio/wav")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload_audio/")
async def upload_audio(audio_file_label: str = Form(...), file: UploadFile = File(...)):
    """
    Upload an audio file for later use as the reference audio.
    """
    try:
        contents = await file.read()

        allowed_extensions = {'wav', 'mp3', 'flac', 'ogg'}
        max_file_size = 5 * 1024 * 1024  # 5MB

        if not file.filename.split('.')[-1] in allowed_extensions:
            return {"error": "Invalid file type. Allowed types are: wav, mp3, flac, ogg"}

        if len(contents) > max_file_size:
            return {"error": "File size is over limit. Max size is 5MB."}

        temp_file = io.BytesIO(contents)
        file_format = magic.from_buffer(temp_file.read(), mime=True)

        if 'audio' not in file_format:
            return {"error": "Invalid file content."}

        file_extension = file.filename.split('.')[-1]
        stored_file_name = f"{audio_file_label}.{file_extension}"

        with open(f"resources/{stored_file_name}", "wb") as f:
            f.write(contents)

        # Also create a WAV version for F5-TTS
        wav_path = f"resources/{audio_file_label}.wav"
        convert_to_wav(f"resources/{stored_file_name}", wav_path)

        return {"message": f"File {file.filename} uploaded successfully with label {audio_file_label}."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/synthesize_speech/")
async def synthesize_speech(
        text: str,
        voice: str,
        accent: Optional[str] = 'en-newest',
        speed: Optional[float] = 1.0,
        watermark: Optional[str] = "@F5-TTS"
):
    """
    Synthesize speech from text using a specified voice and style.
    """
    start_time = time.time()
    try:
        logging.info(f'Generating speech for {voice}')
        if watermark:
            logging.info(f'watermark: {watermark}')

        # First try to find a WAV version
        matching_files = [f for f in os.listdir("resources") if f.startswith(voice) and f.lower().endswith('.wav')]
        
        # If no WAV found, try other formats and convert
        if not matching_files:
            matching_files = [f for f in os.listdir("resources") if f.startswith(voice)]
            if not matching_files:
                raise HTTPException(status_code=400, detail="No matching voice found.")
            
            # Convert to WAV
            input_file = f'resources/{matching_files[0]}'
            wav_path = f'{output_dir}/ref_converted.wav'
            convert_to_wav(input_file, wav_path)
            reference_file = wav_path
        else:
            reference_file = f'resources/{matching_files[0]}'

        # Generate a reference text that matches the input style and length
        input_words = len(text.split())
        # Use the reference text that matches the reference audio file
        if reference_file == f"{resources_dir}/default_en.wav":
            ref_text = default_ref_text
        else:
            ref_text = model.transcribe(reference_file)

        save_path = f'{output_dir}/output_synthesized.wav'

        # Process text in larger chunks instead of individual sentences
        chunks = []
        current_chunk = []
        current_length = 0
        max_chunk_length = 100  # Maximum words per chunk

        for sentence in split_text_into_sentences(text):
            words_in_sentence = len(sentence.split())
            if current_length + words_in_sentence > max_chunk_length and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_length = words_in_sentence
            else:
                current_chunk.append(sentence)
                current_length += words_in_sentence

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        # Process each chunk
        temp_files = []
        for i, chunk in enumerate(chunks):
            logging.info(f"Processing chunk {i+1}/{len(chunks)}")
            temp_path = f'{output_dir}/temp_{i}.wav'
            
            wav, sr, _ = model.infer(
                ref_file=reference_file,
                ref_text=ref_text,
                gen_text=chunk,
                speed=speed,
                file_wave=temp_path
            )
            temp_files.append(temp_path)

        # Concatenate all temporary files with smoother transitions
        if len(temp_files) > 1:
            combined = AudioSegment.empty()
            crossfade_duration = 50  # 50ms crossfade
            
            for i, temp_file in enumerate(temp_files):
                audio = AudioSegment.from_wav(temp_file)
                if i == 0:
                    combined = audio
                else:
                    combined = combined.append(audio, crossfade=crossfade_duration)
            
            combined.export(save_path, format='wav')
        else:
            os.rename(temp_files[0], save_path)

        # Clean up temporary files
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)

        result = StreamingResponse(open(save_path, 'rb'), media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    end_time = time.time()
    elapsed_time = end_time - start_time

    result.headers["X-Elapsed-Time"] = str(elapsed_time)
    result.headers["X-Device-Used"] = device

    # Add CORS headers
    result.headers["Access-Control-Allow-Origin"] = "*"
    result.headers["Access-Control-Allow-Credentials"] = "true"
    result.headers["Access-Control-Allow-Headers"] = "Origin, Content-Type, X-Amz-Date, Authorization, X-Api-Key, X-Amz-Security-Token, locale"
    result.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"

    return result
