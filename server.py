# server.py
import argparse
import logging
import os
import random
import socket
import struct
import threading
import time
import wave

# --- Constants ---
# Default u8 silence is 128 (midpoint of 0-255)
DEFAULT_U8_SILENCE_BYTE_VALUE = 128

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


# --- Helper Functions ---
def get_wav_files(directory):
    """Scans the directory for .wav files."""
    files = [
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.lower().endswith(".wav")
    ]
    logging.info(f"Found {len(files)} WAV files in '{directory}': {files}")
    return files


# Pass expected format parameters
def read_wav_data(filepath, expected_rate, expected_bits, expected_channels):
    """Reads raw audio data from a WAV file, ensuring correct format."""
    try:
        with wave.open(filepath, "rb") as wf:
            rate = wf.getframerate()
            # Use passed arguments for validation
            if rate != expected_rate:
                logging.warning(
                    f"Skipping {filepath}: Incorrect sample rate "
                    f"({rate} Hz). Expected {expected_rate} Hz."
                )
                return None
            sampwidth_bits = wf.getsampwidth() * 8
            # Use passed arguments for validation
            if sampwidth_bits != expected_bits:
                logging.warning(
                    f"Skipping {filepath}: Incorrect bit depth "
                    f"({sampwidth_bits}-bit). Expected {expected_bits}-bit."
                )
                return None
            nchannels = wf.getnchannels()
            # Use passed arguments for validation
            if nchannels != expected_channels:
                logging.warning(
                    f"Skipping {filepath}: Incorrect channel count "
                    f"({nchannels}). Expected {expected_channels}."
                )
                return None

            frames = wf.readframes(wf.getnframes())
            logging.info(f"Read {len(frames)} bytes from {filepath}")
            return frames
    except wave.Error as e:
        # Shortened line 89
        logging.error(f"Error reading WAV {filepath}: {e}")
        return None
    except FileNotFoundError:
        # Shortened line 96
        logging.error(f"WAV file not found: {filepath}")
        return None


# --- Client Handling ---
# Updated signature later to accept config
def handle_client(conn, addr, wav_files, config):
    """Handles a single client connection."""
    logging.info(f"Connected by {addr}")
    client_active = True
    wav_indices = list(range(len(wav_files)))  # Indices to shuffle

    try:
        while client_active:
            # Shuffle order for this loop iteration
            random.shuffle(wav_indices)
            for index in wav_indices:
                filepath = wav_files[index]
                logging.info(f"[{addr}] Streaming file: {filepath}")
                # Pass config values to read_wav_data
                audio_data = read_wav_data(
                    filepath,
                    config.sample_rate,
                    config.bits,
                    config.channels
                )

                if audio_data is None:
                    logging.warning(f"[{addr}] Skipping file: {filepath}")
                    continue  # Skip to the next file if this one is bad

                # Stream the audio data in chunks
                start_time = time.monotonic()
                bytes_sent_total = 0
                # loop_start_time removed (unused)
                # Use config values for chunking and timing
                chunk_size_bytes = config.chunk_size_bytes
                bytes_per_sec = config.bytes_per_sec

                for i in range(0, len(audio_data), chunk_size_bytes):
                    chunk = audio_data[i: i + chunk_size_bytes]
                    if not chunk:
                        break  # End of data

                    try:
                        conn.sendall(chunk)
                        bytes_sent_total += len(chunk)

                        # Calculate expected time for chunk and sleep if needed
                        # Removed comment line 112
                        elapsed_time_file = time.monotonic() - start_time
                        # bytes_per_sec already calculated above
                        expected_time_file = bytes_sent_total / bytes_per_sec
                        sleep_time = expected_time_file - elapsed_time_file
                        if sleep_time > 0:
                            time.sleep(sleep_time)
                        # else: we are falling behind, log potentially?
                        # logging.warning(
                        #    f"[{addr}] Falling behind: {sleep_time:.4f}s"
                        # )

                    except (BrokenPipeError, ConnectionResetError):
                        logging.info(f"Client {addr} disconnected.")
                        client_active = False
                        break
                    except Exception as e:
                        logging.error(f"Error sending data to {addr}: {e}")
                        client_active = False
                        break

                if not client_active:
                    break  # Exit outer loop if client disconnected

                # Send silence between files
                logging.info(f"[{addr}] {config.silence_ms}ms silence")
                try:
                    conn.sendall(config.silence_bytes)
                    # Add silence duration to timing calculation
                    # Next file's start_time accounts for silence
                    # silence_start_time removed (unused)
                    # bytes_per_sec already calculated above
                    silence_dur = len(config.silence_bytes) / bytes_per_sec
                    # Sleep for the calculated silence duration
                    # Assumes sendall is relatively quick
                    time.sleep(max(0, silence_dur))

                    # Reset start time for the next file's pacing
                    start_time = time.monotonic()
                    bytes_sent_total = 0  # Reset byte count

                except (BrokenPipeError, ConnectionResetError):
                    logging.info(f"Client {addr} disconnected during silence.")
                    client_active = False
                    break
                except Exception as e:
                    logging.error(f"Error sending silence to {addr}: {e}")
                    client_active = False
                    break

            if not client_active:
                break  # Exit outer loop if client disconnected

            # Small sleep at the end of the loop to prevent
            # tight spinning if no files
            if not wav_files:
                time.sleep(1)

    except Exception as e:
        logging.error(f"Client handler exception for {addr}: {e}")
    finally:
        logging.info(f"Closing connection to {addr}")
        conn.close()


# --- Server Main Logic ---
def start_server(config):
    """Starts the TCP server using the provided config."""
    audio_dir = config.audio_dir
    if not os.path.exists(audio_dir):
        logging.error(
            f"Audio dir '{audio_dir}' not found. Please create it."
        )
        # Attempt to create the directory if it doesn't exist
        try:
            os.makedirs(audio_dir)
            logging.info(f"Created audio directory: '{audio_dir}'")
        except OSError as e:
            logging.error(f"Failed creating audio dir '{audio_dir}': {e}")
            return

    if not os.path.isdir(audio_dir):
        logging.error(f"'{audio_dir}' exists but is not a directory.")
        return

    wav_files = get_wav_files(audio_dir)
    if not wav_files:
        logging.warning(
            f"No WAV files in '{audio_dir}'. Server will stream silence/wait."
        )
        # Client handler loop handles empty list case

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Allow reuse of address
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((config.host, config.port))
            s.listen()
            logging.info(f"Server listening on {config.host}:{config.port}")
            abs_audio_dir = os.path.abspath(audio_dir)
            logging.info(f"Streaming from: {abs_audio_dir}")
            # Fix line length L224
            logging.info(
                f"Format: {config.sample_rate} Hz, {config.bits}-bit "
                f"{config.channels}-channel"
            )
            logging.info(f"Chunk Duration: {config.chunk_ms}ms")
            logging.info(f"Silence Between Files: {config.silence_ms}ms")

            while True:
                try:
                    conn, addr = s.accept()
                    # Refresh the list of wav files for each new connection
                    # Use the *configured* audio dir
                    current_wav_files = get_wav_files(config.audio_dir)
                    if not current_wav_files:
                        logging.warning(
                            f"No WAV files in '{config.audio_dir}'\
                                  for client {addr}."
                        )
                    # Pass config down to client handler
                    client_thread = threading.Thread(
                        target=handle_client,
                        args=(conn, addr, list(current_wav_files), config),
                        daemon=True,
                    )
                    client_thread.start()
                except Exception as e:
                    logging.error(f"Error accepting/starting thread: {e}")

        except OSError as e:
            logging.error(f"Server failed to bind or listen: {e}")
        except KeyboardInterrupt:
            logging.info("Server shutting down.")
        finally:
            logging.info("Server stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TCP Audio Stream Server")
    parser.add_argument(
        '--host', default='0.0.0.0',
        help='Host address to bind the server to (default: 0.0.0.0)')
    parser.add_argument(
        '--port', type=int, default=65432,
        help='Port number to listen on (default: 65432)')
    parser.add_argument(
        '--audio-dir', required=True,
        help='Directory containing WAV files to stream')
    parser.add_argument(
        '--sample-rate', type=int, default=16000,
        help='Expected sample rate (Hz, default: 16000)')
    parser.add_argument(
        '--bits', type=int, default=8, choices=[8, 16],
        help='Expected bits per sample (8 or 16, default: 8)')
    parser.add_argument(
        '--channels', type=int, default=1, choices=[1, 2],
        help='Expected channels (1 or 2, default: 1)')
    parser.add_argument(
        '--chunk-ms', type=int, default=20,
        help='Chunk duration (ms, default: 20)')
    parser.add_argument(
        '--silence-ms', type=int, default=10,
        help='Silence duration between files (ms, default: 10)')

    args = parser.parse_args()

    # --- Calculate derived configuration values ---
    args.bytes_per_sample = (args.bits // 8) * args.channels
    args.chunk_size_samples = int(args.sample_rate * (args.chunk_ms / 1000))
    args.chunk_size_bytes = args.chunk_size_samples * args.bytes_per_sample
    args.silence_samples = int(args.sample_rate * (args.silence_ms / 1000))

    # Determine silence byte value based on bit depth
    if args.bits == 8:
        silence_val = DEFAULT_U8_SILENCE_BYTE_VALUE
        num_silence_bytes = args.silence_samples * args.bytes_per_sample
        silence_bytes_list = [silence_val] * num_silence_bytes
        args.silence_bytes = bytes(silence_bytes_list)
    elif args.bits == 16:
        # For 16-bit PCM, silence is typically 0.
        # Pack '0' as little-endian signed short ('<h') per sample/channel.
        silence_val = 0
        silence_sample_bytes = struct.pack('<h', silence_val) * args.channels
        args.silence_bytes = silence_sample_bytes * args.silence_samples
    else:
        # Should not happen due to argparse choices, but good practice
        logging.error(f"Unsupported bit depth: {args.bits}. Exiting.")
        exit(1)

    # Calculate bytes per second AFTER calculating bytes_per_sample
    args.bytes_per_sec = args.sample_rate * args.bytes_per_sample

    start_server(args)
