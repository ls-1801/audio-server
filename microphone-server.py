import socket
import threading
import pyaudio
import struct
import time

class AudioTCPServer:
    def __init__(self, host='0.0.0.0', port=5555, sample_rate=44100, sample_width=2):
        """
        Initialize the audio TCP server.
        
        Args:
            host (str): Host IP address to bind to
            port (int): Port number to listen on
            sample_rate (int): Audio sample rate in Hz (e.g., 44100, 48000)
            sample_width (int): Sample width in bytes (1=8bit, 2=16bit, 4=32bit)
        """
        self.host = host
        self.port = port
        self.sample_rate = sample_rate
        self.sample_width = sample_width
        self.chunk_size = 1024  # Number of frames per buffer
        self.clients = []
        self.running = False
        self.lock = threading.Lock()
        
        # Initialize PyAudio
        self.p = pyaudio.PyAudio()
        
        # Map sample width to PyAudio format
        self.format_map = {
            1: pyaudio.paInt8,
            2: pyaudio.paInt16,
            4: pyaudio.paInt32
        }
        
        if sample_width not in self.format_map:
            raise ValueError(f"Unsupported sample width: {sample_width}. Use 1, 2, or 4.")
        
        self.format = self.format_map[sample_width]
        
    def start_server(self):
        """Start the TCP server and audio streaming."""
        self.running = True
        
        # Start microphone thread
        mic_thread = threading.Thread(target=self._audio_stream)
        mic_thread.daemon = True
        mic_thread.start()
        
        # Set up server socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            print(f"Audio server listening on {self.host}:{self.port}")
            print(f"Configuration: {self.sample_rate}Hz, {self.sample_width*8}bit")
            
            while self.running:
                try:
                    server_socket.settimeout(1.0)
                    client_socket, address = server_socket.accept()
                    print(f"Client connected from {address}")
                    
                    # Send audio configuration to client
                    config = struct.pack('!III', self.sample_rate, self.sample_width, self.chunk_size)
                    client_socket.send(config)
                    
                    with self.lock:
                        self.clients.append(client_socket)
                        
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"Error accepting client: {e}")
    
    def _audio_stream(self):
        """Capture audio from microphone and broadcast to clients."""
        try:
            # Open microphone stream
            stream = self.p.open(
                format=self.format,
                channels=1,  # Mono audio
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            print("Microphone stream started")
            
            while self.running:
                try:
                    # Read audio data from microphone
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    
                    # Broadcast to all connected clients
                    with self.lock:
                        disconnected_clients = []
                        
                        for client in self.clients:
                            try:
                                client.send(data)
                            except (socket.error, BrokenPipeError):
                                disconnected_clients.append(client)
                        
                        # Remove disconnected clients
                        for client in disconnected_clients:
                            self.clients.remove(client)
                            client.close()
                            print("Client disconnected")
                            
                except Exception as e:
                    print(f"Audio stream error: {e}")
                    time.sleep(0.1)
            
            stream.stop_stream()
            stream.close()
            
        except Exception as e:
            print(f"Error setting up audio stream: {e}")
    
    def stop_server(self):
        """Stop the server and clean up resources."""
        self.running = False
        
        with self.lock:
            for client in self.clients:
                client.close()
            self.clients.clear()
        
        self.p.terminate()
        print("Server stopped")


# Example client code to receive and play audio
class AudioTCPClient:
    def __init__(self, host='localhost', port=5555):
        self.host = host
        self.port = port
        self.p = pyaudio.PyAudio()
        
    def connect_and_play(self):
        """Connect to server and play received audio."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((self.host, self.port))
            print(f"Connected to {self.host}:{self.port}")
            
            # Receive audio configuration
            config_data = client_socket.recv(12)
            sample_rate, sample_width, chunk_size = struct.unpack('!III', config_data)
            
            format_map = {
                1: pyaudio.paInt8,
                2: pyaudio.paInt16,
                4: pyaudio.paInt32
            }
            
            # Open output stream
            stream = self.p.open(
                format=format_map[sample_width],
                channels=1,
                rate=sample_rate,
                output=True,
                frames_per_buffer=chunk_size
            )
            
            print(f"Playing audio: {sample_rate}Hz, {sample_width*8}bit")
            
            try:
                while True:
                    data = client_socket.recv(chunk_size * sample_width)
                    if not data:
                        break
                    stream.write(data)
            except KeyboardInterrupt:
                print("Client stopped")
            finally:
                stream.stop_stream()
                stream.close()
                self.p.terminate()


if __name__ == "__main__":
    # Server example
    server = AudioTCPServer(
        host='0.0.0.0',
        port=5555,
        sample_rate=44100,  # Configure sample rate
        sample_width=2      # Configure sample width (2 = 16-bit)
    )
    
    try:
        server.start_server()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.stop_server()
