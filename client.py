# client.py
import argparse
import logging
import socket
import sys

import pyaudio

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def play_stream(config):
    """Connects to the server and plays the received audio stream."""

    # --- PyAudio Setup ---
    p = pyaudio.PyAudio()

    # Map bits to PyAudio format
    if config.bits == 8:
        audio_format = pyaudio.paUInt8  # Unsigned 8-bit
    elif config.bits == 16:
        # Signed 16-bit Little Endian (common)
        audio_format = pyaudio.paInt16
    else:
        logging.error(f"Unsupported bit depth for playback: {config.bits}")
        p.terminate()
        return

    try:
        stream = p.open(format=audio_format,
                        channels=config.channels,
                        rate=config.sample_rate,
                        output=True,
                        frames_per_buffer=config.buffer_size)
    except OSError as e:
        logging.error(f"Failed to open PyAudio stream: {e}")
        logging.error(
            "Ensure correct audio output device and PyAudio install."
        )
        p.terminate()
        return

    # --- Socket Connection ---
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            logging.info(f"Connecting to {config.host}:{config.port}...")
            s.connect((config.host, config.port))
            logging.info("Connected. Receiving audio stream...")

            while True:
                try:
                    # Receive data in chunks matching buffer size
                    data = s.recv(config.buffer_size)
                    if not data:
                        logging.info("Stream ended (server disconnected).")
                        break
                    # Write received data to the audio stream
                    stream.write(data)
                except socket.error as e:
                    logging.error(f"Socket error during recv: {e}")
                    break
                except IOError as e:
                    # This can happen if the audio device has issues
                    logging.error(f"PyAudio stream write error: {e}")
                    break
                except KeyboardInterrupt:
                    logging.info("Playback stopped by user.")
                    break

    except socket.error as e:
        logging.error(f"Connection failed {config.host}:{config.port}: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
    finally:
        # --- Cleanup ---
        logging.info("Cleaning up...")
        if 'stream' in locals() and stream.is_active():
            stream.stop_stream()
            stream.close()
            logging.info("PyAudio stream closed.")
        p.terminate()
        logging.info("PyAudio terminated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TCP Audio Stream Client")
    parser.add_argument(
        '--host', default='localhost',
        help='Server host address (default: localhost)')
    parser.add_argument(
        '--port', type=int, default=65432,
        help='Server port number (default: 65432)')
    # Audio format arguments should match the server's output
    parser.add_argument(
        '--sample-rate', type=int, default=16000,
        help='Audio sample rate (Hz, default: 16000)')
    parser.add_argument(
        '--bits', type=int, default=8, choices=[8, 16],
        help='Audio bits per sample (8 or 16, default: 8)')
    parser.add_argument(
        '--channels', type=int, default=1, choices=[1, 2],
        help='Audio channels (1 or 2, default: 1)')
    parser.add_argument(
        '--buffer-size', type=int, default=1024,
        help='Audio buffer size for playback (bytes, default: 1024)')

    args = parser.parse_args()

    # Basic validation
    if args.buffer_size <= 0:
        logging.error("Buffer size must be positive.")
        sys.exit(1)

    play_stream(args)
