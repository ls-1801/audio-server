import argparse
import base64
import numpy as np
import pyaudio
import sys
import wave
import os
import logging
from datetime import datetime
import struct

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def decode_base64_audio(input_file, output_file=None, sample_rate=16000, channels=1, play_audio=False, output_bit_depth=16):
    """
    Reads a file containing base64-encoded 32-bit floating point audio data and decodes it.
    Format of each line: start_timestamp,end_timestamp,number_samples,base64_encoded_data

    Parameters:
        input_file (str): Path to input file with base64 encoded data
        output_file (str): Path to output WAV file (optional)
        sample_rate (int): Sample rate in Hz
        channels (int): Number of audio channels
        play_audio (bool): Whether to play the audio during processing
        output_bit_depth (int): Bit depth for output WAV file (8 or 16)
    """
    # Set up output audio format
    if output_bit_depth == 8:
        output_dtype = np.uint8
        pyaudio_format = pyaudio.paUInt8
        wave_sampwidth = 1
        max_value = 255
    else:  # 16-bit
        output_dtype = np.int16
        pyaudio_format = pyaudio.paInt16
        wave_sampwidth = 2
        max_value = 32767

    # Set up audio playback if requested
    p = None
    stream = None
    if play_audio:
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio_format,
            channels=channels,
            rate=sample_rate,
            output=True
        )

    # Set up WAV output if requested
    wav_file = None
    if output_file:
        wav_file = wave.open(output_file, 'wb')
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(wave_sampwidth)  # bytes per sample
        wav_file.setframerate(sample_rate)

    # Stats
    total_samples = 0
    total_chunks = 0
    decoded_samples = []  # Store all decoded samples if output_file is specified

    try:
        with open(input_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    # Skip empty lines or commented lines
                    if not line.strip() or line.strip().startswith('#'):
                        continue

                    # Parse the line
                    parts = line.strip().split(',')
                    if len(parts) < 4:
                        logging.warning(f"Line {line_num}: Invalid format (expected 4 parts, got {len(parts)})")
                        continue

                    start_timestamp = parts[0]
                    end_timestamp = parts[1]
                    num_samples = int(parts[2])
                    base64_data = parts[3]

                    # Decode base64 data
                    binary_data = base64.b64decode(base64_data)

                    # Convert to numpy array of 32-bit floats (little endian)
                    float_samples = np.frombuffer(binary_data, dtype=np.float32)

                    # Verify number of samples
                    if len(float_samples) != num_samples:
                        logging.warning(
                            f"Line {line_num}: Sample count mismatch. Expected {num_samples}, got {len(float_samples)}"
                        )

                    # Print summary for this chunk
                    logging.info(f"Chunk {line_num}: {start_timestamp} to {end_timestamp}, {len(float_samples)} samples")
                    if len(float_samples) > 0:
                        min_val = np.min(float_samples)
                        max_val = np.max(float_samples)
                        avg_val = np.mean(float_samples)
                        logging.info(f"  Float range: {min_val:.6f} to {max_val:.6f}, Average: {avg_val:.6f}")

                    # Convert float32 [-1.0, 1.0] to output format (int16 or uint8)
                    # First clip to [-1.0, 1.0] to handle any out-of-range values
                    float_samples = np.clip(float_samples, -1.0, 1.0)

                    if output_bit_depth == 8:
                        # For 8-bit audio, scale and shift to [0, 255]
                        int_samples = (((float_samples + 1.0) / 2.0) * 255.0).astype(output_dtype)
                    else:
                        # For 16-bit audio, scale to [-32768, 32767]
                        int_samples = (float_samples * 32767.0).astype(output_dtype)

                    # Play audio if requested
                    if play_audio and stream and len(int_samples) > 0:
                        stream.write(int_samples.tobytes())

                    # Write to WAV file if requested
                    if wav_file:
                        wav_file.writeframes(int_samples.tobytes())
                        decoded_samples.extend(int_samples)

                    # Update stats
                    total_samples += len(float_samples)
                    total_chunks += 1

                except Exception as e:
                    logging.error(f"Error processing line {line_num}: {e}")

        # Print final stats
        logging.info(f"Processing complete.")
        logging.info(f"Total chunks: {total_chunks}")
        logging.info(f"Total samples: {total_samples}")

        # Calculate duration
        duration_sec = total_samples / sample_rate
        logging.info(f"Audio duration: {duration_sec:.2f} seconds")

        # Save decoded samples to numpy array file for further analysis if requested
        if output_file:
            # Save float32 version
            np_output_file = os.path.splitext(output_file)[0] + '_float32.npy'
            float_array = np.frombuffer(binary_data, dtype=np.float32)
            np.save(np_output_file, float_array)
            logging.info(f"Saved raw float32 samples to NumPy file: {np_output_file}")

            # Save converted version
            np_output_file = os.path.splitext(output_file)[0] + f'_{output_bit_depth}bit.npy'
            decoded_samples_array = np.array(decoded_samples, dtype=output_dtype)
            np.save(np_output_file, decoded_samples_array)
            logging.info(f"Saved converted {output_bit_depth}-bit samples to NumPy file: {np_output_file}")

        return True

    except Exception as e:
        logging.error(f"Error: {e}")
        return False
    finally:
        # Clean up resources
        if stream:
            stream.stop_stream()
            stream.close()
        if p:
            p.terminate()
        if wav_file:
            wav_file.close()
            if output_file:
                logging.info(f"Saved WAV file: {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Decode base64 float32 audio data from file")
    parser.add_argument('input_file', help='Input file containing base64 encoded 32-bit float audio data')
    parser.add_argument('--output', '-o', help='Output WAV file')
    parser.add_argument('--output-bit-depth', '-b', type=int, choices=[8, 16], default=16,
                        help='Output audio bit depth (8 or 16)')
    parser.add_argument('--sample-rate', '-r', type=int, default=16000,
                        help='Audio sample rate in Hz')
    parser.add_argument('--channels', '-c', type=int, choices=[1, 2], default=1,
                        help='Number of audio channels')
    parser.add_argument('--play', '-p', action='store_true',
                        help='Play audio during processing')

    args = parser.parse_args()

    # Generate default output filename if not specified
    if not args.output and args.play is False:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"decoded_audio_{timestamp}.wav"
        logging.info(f"No output file specified. Using default: {args.output}")

    # Run the decoder
    success = decode_base64_audio(
        args.input_file,
        args.output,
        args.sample_rate,
        args.channels,
        args.play,
        args.output_bit_depth
    )

    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
