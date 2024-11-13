import struct
import pandas as pd
import time
import tkinter as tk
from tkinter import filedialog

class OsdFileReader:
    def __init__(self, file_path):
        self.file_path = file_path
        self.header = {}
        self.frame_data = pd.DataFrame(columns=["timestamp", "frameNumber", "frameSize", "frameContent"])
        self.parsed_data_df = None  # Dictionary to store parsed data for each frame
        self.frame_rate = None
        self.duration = None
        self.load_file()

    def load_file(self):
        with open(self.file_path, 'rb') as file:
            # Parse header
            self.header['magic'] = file.read(7).decode('utf-8')
            self.header['version'], = struct.unpack('<H', file.read(2))
            self.header['config'] = {
                'charWidth': struct.unpack('<B', file.read(1))[0],
                'charHeight': struct.unpack('<B', file.read(1))[0],
                'fontWidth': struct.unpack('<B', file.read(1))[0],
                'fontHeight': struct.unpack('<B', file.read(1))[0],
                'xOffset': struct.unpack('<H', file.read(2))[0],
                'yOffset': struct.unpack('<H', file.read(2))[0],
                'fontVariant': file.read(5).decode('utf-8').strip('\x00')
            }

            # Read frames based on version
            frames = []
            while True:
                try:
                    if self.header['version'] == 3:
                        # Version 3: Timestamp + Frame Size
                        timestamp, = struct.unpack('<d', file.read(8))
                        frame_size, = struct.unpack('<I', file.read(4))
                        frame_data = file.read(frame_size)
                        frames.append({
                            "timestamp": timestamp,
                            "frameNumber": None,
                            "frameSize": frame_size,
                            "frameContent": frame_data
                        })
                    else:
                        # Versions 1 and 2: Frame Number + Frame Size
                        frame_number, frame_size = struct.unpack('<II', file.read(8))
                        frame_data = file.read(frame_size)
                        frames.append({
                            "timestamp": None,
                            "frameNumber": frame_number,
                            "frameSize": frame_size,
                            "frameContent": frame_data
                        })
                except (struct.error, EOFError):
                    break  # End of file reached or incomplete frame data

            self.frame_data = pd.DataFrame(frames)

    def print_info(self):
        print("Header Information:")
        print(f"Magic: {self.header['magic']}")
        print(f"Version: {self.header['version']}")
        print("Config:")
        for key, value in self.header['config'].items():
            print(f"  {key}: {value}")

        print("\nFrame Data Summary:")
        print(f"Total Frames: {self.get_frame_count()}")
        print(f"Duration: {self.get_duration()} seconds")
        print(f"Frame Rate: {self.calculate_frame_rate()} fps")

    def get_data(self):
        """Returns the frame data as a DataFrame for external processing."""
        return self.frame_data

    def generate_pseudo_frames(self, frame_rate):
        """Generate pseudo timestamps or frame numbers based on the frame rate."""
        self.frame_rate = frame_rate
        if "timestamp" in self.frame_data.columns and self.frame_data["timestamp"].isnull().all():
            # Generate timestamps based on frame numbers and frame rate
            self.frame_data["timestamp"] = self.frame_data["frameNumber"] / frame_rate
        elif "frameNumber" in self.frame_data.columns and self.frame_data["frameNumber"].isnull().all():
            # Generate frame numbers based on timestamps and frame rate
            self.frame_data["frameNumber"] = (self.frame_data["timestamp"] * frame_rate).astype(int)

    def print_frame(self, frame_index):
        """Print a single frame's content in a readable format."""
        try:
            frame = self.frame_data.iloc[frame_index]
            content = frame["frameContent"]
            char_width = self.header["config"]["charWidth"]
            char_height = self.header["config"]["charHeight"]

            print(f"\nFrame {frame_index}:")
            for y in range(char_height):
                line = ' '.join(f"{content[y * char_width + x]:02X}" for x in range(char_width))
                print(line)
        except IndexError:
            print("Frame index out of bounds.")

    def calculate_frame_rate(self):
        """Calculate the frame rate based on timestamps if available."""
        if self.header['version'] == 3 and not self.frame_data["timestamp"].isnull().all():
            # Calculate frame rate using timestamps
            timestamps = self.frame_data["timestamp"].dropna()
            if len(timestamps) > 1:
                frame_intervals = timestamps.diff().dropna()
                self.frame_rate = 1 / frame_intervals.mean()
            else:
                self.frame_rate = None
        return self.frame_rate

    def get_frame_count(self):
        """Return the total number of frames."""
        return len(self.frame_data)

    def get_duration(self):
        """Return the total duration of the frames in seconds."""
        if self.header['version'] == 3 and not self.frame_data["timestamp"].isnull().all():
            self.duration = self.frame_data["timestamp"].max()
        elif self.frame_rate:
            self.duration = self.get_frame_count() / self.frame_rate
        return self.duration

    def statistics(self):
        """Print summary statistics about the .osd file."""
        print("OSD File Statistics:")
        print(f"Total Frames: {self.get_frame_count()}")
        print(f"Duration: {self.get_duration()} seconds")
        print(f"Frame Rate: {self.calculate_frame_rate()} fps")

    def parse(self, field_definitions):
        """
        Parse specified fields in each frame using the provided field definitions.
        :param field_definitions: dict containing parsing instructions for each field.
        """
        # Initialize an empty DataFrame with columns for each field definition
        self.parsed_data_df = pd.DataFrame(index=self.frame_data.index, columns=field_definitions.keys())

        # Iterate over each frame in the OSD data
        for frame_index, frame in self.frame_data.iterrows():
            frame_content = frame["frameContent"]  # Raw frame data (byte array)

            for field_name, (identifier, coordinates, length, format_type) in field_definitions.items():
                try:
                    # Determine the starting position in the frame content
                    start_pos = None
                    if identifier != -1:
                        # Locate the identifier within the frame content
                        start_pos = self._find_identifier_in_grid(frame_content, identifier)
                        if start_pos is None:
                            continue  # Skip if identifier not found
                        # Adjust start position to exclude the identifier itself
                        start_pos += 1 if length > 0 else -1
                    elif coordinates != [-1, -1]:
                        # Use specific coordinates if identifier is -1
                        x, y = coordinates
                        start_pos = (y * self.header["config"]["charWidth"]) + x
                    else:
                        # Skip if both identifier and coordinates are invalid
                        continue

                    # Adjust for negative lengths (leftward parsing)
                    if length < 0:
                        start_pos += length  # Move left by the absolute value of `length`

                    # Validate if the position and length are within frame bounds
                    length = abs(length)  # Use absolute length for reading
                    if start_pos < 0 or start_pos + length > len(frame_content):
                        raise IndexError("Reading beyond frame bounds")

                    # Extract the specified length of data starting from start_pos
                    data_bytes = frame_content[start_pos:start_pos + length]
                    data_hex = ''.join(f"{byte:02X}" for byte in data_bytes)

                    # Parse the data based on format_type
                    if format_type == 0:  # String
                        parsed_value = bytes.fromhex(data_hex).decode('utf-8', errors='ignore')
                    elif format_type == 1:  # Float
                        parsed_value = float.fromhex(data_hex)
                    elif format_type == 2:  # Time (mm:ss)
                        minutes = int(data_hex[:2], 16)
                        seconds = int(data_hex[2:], 16)
                        parsed_value = f"{minutes:02}:{seconds:02}"
                    else:
                        raise ValueError("Unknown format type")

                    # Store the parsed value in the parsed_data_df DataFrame
                    self.parsed_data_df.at[frame_index, field_name] = parsed_value

                except (IndexError, ValueError) as e:
                    # Catch parsing errors and continue to the next field
                    print(f"Error parsing field '{field_name}' in frame {frame_index}: {e}")
                    continue

    def _find_identifier_in_grid(self, frame_content, identifier):
        """
        Finds the position of an identifier in the frame content (byte array).
        :param frame_content: The content of the frame (byte array).
        :param identifier: The identifier to search for.
        :return: The index of the identifier in the frame content, or None if not found.
        """
        try:
            identifier_bytes = bytes([identifier])
            return frame_content.index(identifier_bytes[0])
        except ValueError:
            return None  # Identifier not found

    # Helper function to open file dialog and create OsdFileReader instance
    @staticmethod
    def open_file_dialog():
        root = tk.Tk()
        root.withdraw()  # Hide the root window

        file_path = filedialog.askopenfilename(
            title="Select OSD File",
            filetypes=[("OSD Files", "*.osd"), ("All Files", "*.*")]
        )

        if file_path:
            osd_reader = OsdFileReader(file_path)
            osd_reader.print_info()
            return osd_reader
        else:
            print("No file selected.")
            return None
