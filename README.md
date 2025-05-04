# Audio Server Project

This project implements a client-server application for streaming audio files over TCP. The server reads WAV files from a specified directory and streams them to connected clients, which then play the audio using PyAudio.

## Description

The server (`server.py`) listens for incoming TCP connections. When a client connects, the server reads WAV files from the configured audio directory, validates their format (sample rate, bit depth, channels), and streams the raw audio data in chunks. It inserts configurable silence between files.

The client (`client.py`) connects to the server, receives the audio stream, and plays it back using the PyAudio library. Both the server and client require matching audio format parameters (sample rate, bits, channels).

## Installation

1.  **Clone the repository (if applicable):**
    ```bash
    git clone <repository-url>
    cd audio-server
    ```
2.  **Install dependencies:**
    Ensure you have Python and `pip` installed. Then, install the required packages:
    ```bash
    pip install -r requirements.txt
    ```
    *Note: PyAudio might have system-level dependencies (like `portaudio`) depending on your OS. Refer to PyAudio documentation if installation fails.*

3.  **Prepare Audio Data:**
    -   Place the WAV audio files you want to stream into a directory.
    -   The project includes `speech_commands_test_set_v0.02.tar.gz`. You might need to extract it (`tar -xzf speech_commands_test_set_v0.02.tar.gz`) and use the resulting directory (or a subdirectory like `audio/`) as the audio source.
    -   Ensure the WAV files match the format parameters (sample rate, bits, channels) you intend to use. The server will skip files that don't match.

## Usage

### Server

Run the server script, specifying the directory containing your WAV files. You can customize other parameters as needed.

**Required:**
*   `--audio-dir`: Path to the directory containing WAV files.

**Optional (with defaults):**
*   `--host`: Host address to bind to (default: `0.0.0.0` - listens on all interfaces).
*   `--port`: Port number to listen on (default: `65432`).
*   `--sample-rate`: Expected audio sample rate in Hz (default: `16000`).
*   `--bits`: Expected bits per sample (default: `8`, choices: `8`, `16`).
*   `--channels`: Expected number of audio channels (default: `1`, choices: `1`, `2`).
*   `--chunk-ms`: Duration of audio chunks to send in milliseconds (default: `20`).
*   `--silence-ms`: Duration of silence to insert between files in milliseconds (default: `10`).

**Example:**
```bash
python server.py --audio-dir ./audio --sample-rate 16000 --bits 8 --channels 1
```

### Client

Run the client script in a separate terminal. Ensure the audio format parameters match the server's configuration.

**Optional (with defaults):**
*   `--host`: Server host address to connect to (default: `localhost`).
*   `--port`: Server port number (default: `65432`).
*   `--sample-rate`: Audio sample rate in Hz (default: `16000`). Must match server.
*   `--bits`: Audio bits per sample (default: `8`, choices: `8`, `16`). Must match server.
*   `--channels`: Audio channels (default: `1`, choices: `1`, `2`). Must match server.
*   `--buffer-size`: Client-side audio playback buffer size in bytes (default: `1024`).

**Example (connecting to a local server with default settings):**
```bash
python client.py --sample-rate 16000 --bits 8 --channels 1
```

**Example (connecting to a remote server):**
```bash
python client.py --host 192.168.1.100 --port 65432 --sample-rate 16000 --bits 8 --channels 1
```

## Project Structure

-   `server.py`: The TCP audio streaming server script.
-   `client.py`: The TCP audio streaming client script with playback.
-   `requirements.txt`: Python dependencies (`PyAudio`).
-   `audio/`: Example directory containing audio files (if extracted from the archive).
-   `speech_commands_test_set_v0.02.tar.gz`: Archive potentially containing the audio dataset.
