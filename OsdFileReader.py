import struct
import pandas as pd
import time
import tkinter as tk
from tkinter import filedialog


class OsdFileReader:
    def __init__(self, file_path, framerate=60):
        self.file_path = file_path
        self.header = {}
        self.frame_data = pd.DataFrame(columns=["timestamp", "frameNumber", "frameSize", "frameContent"])
        self.parsed_data_df = None  # will hold parsed data from user-defined parse() calls
        self.frame_rate = framerate
        self.duration = None
        self.load_file()

    def load_file(self):
        with open(self.file_path, 'rb') as file:
            # Read 40 bytes to see if last 4 bytes are "DJO3"
            first_40 = file.read(40)
            if len(first_40) < 40:
                # Not even a 40-byte header, fallback to old format
                file.seek(0)
                self._parse_old_format(file)
                return

            # Check if last 4 bytes are "DJO3"
            if first_40[-4:] == b"DJO3":
                # We have the new DJO3 format
                self._parse_djo3_format(file, first_40)
            else:
                # Fall back to older .osd version logic
                file.seek(0)
                self._parse_old_format(file)

        # Once frames are loaded, generate timestamps or frameNumbers if needed
        self.generate_pseudo_frames(self.frame_rate)

    def _parse_djo3_format(self, file, header_bytes):
        """
        Parse the new DJO3 file structure:
         - 40-byte header (already read as header_bytes)
         - Repeated frames of:
             [4 bytes of delta_time in ms] + [1060 x 2 bytes (uint16_t each)]
        """
        # Break down the 40-byte header
        firmware_part = header_bytes[:4]  # 4 bytes from font.txt
        header_part = header_bytes[4:36]  # next 32 bytes
        signature = header_bytes[36:40]  # "DJO3"

        # Store it in self.header
        self.header['magic'] = firmware_part.decode('utf-8', errors='ignore').strip('\x00')
        # We'll designate version=99 as "DJO3"
        self.header['version'] = 99

        # Hardcode charWidth and charHeight for the new format
        # so other parts of the code won't break when they query them.
        self.header['config'] = {
            'charWidth': 53,
            'charHeight': 20,
            'fontWidth': 0,
            'fontHeight': 0,
            'xOffset': 0,
            'yOffset': 0,
            'fontVariant': '',
            'headerPart': header_part.decode('utf-8', errors='ignore'),
            'signature': signature.decode('utf-8')
        }

        frames = []
        while True:
            # Try reading 4 bytes for delta_time
            time_data = file.read(4)
            if len(time_data) < 4:
                break  # End of file

            (delta_time_ms,) = struct.unpack('<I', time_data)
            # Convert ms -> seconds
            timestamp_sec = float(delta_time_ms) / 1000.0

            # Read 1060 x 2 bytes = 2120 bytes
            frame_bytes = file.read(1060 * 2)
            if len(frame_bytes) < (1060 * 2):
                break  # End of file or incomplete data

            # Convert these 2120 bytes into a list of 16-bit ints
            frame_content = []
            for i in range(0, len(frame_bytes), 2):
                val = struct.unpack('<H', frame_bytes[i:i + 2])[0]
                frame_content.append(val)

            # Store the frame in our DataFrame
            frames.append({
                "timestamp": timestamp_sec,
                "frameNumber": None,
                "frameSize": 1060,  # The length in 16-bit words
                "frameContent": frame_content
            })

        # Convert the list of frames into a DataFrame
        self.frame_data = pd.DataFrame(frames)

    def _parse_old_format(self, file):
        """
        Fallback for older .osd files, using the existing logic:
         - Read "magic" (7 bytes), version (2 bytes),
           then config including charWidth, etc.
         - Then parse frames based on version 2 or 3.
        """
        self.header['magic'] = file.read(7).decode('utf-8')
        self.header['version'], = struct.unpack('<H', file.read(2))

        # Fill config
        self.header['config'] = {
            'charWidth': struct.unpack('<B', file.read(1))[0],
            'charHeight': struct.unpack('<B', file.read(1))[0],
            'fontWidth': struct.unpack('<B', file.read(1))[0],
            'fontHeight': struct.unpack('<B', file.read(1))[0],
            'xOffset': struct.unpack('<H', file.read(2))[0],
            'yOffset': struct.unpack('<H', file.read(2))[0],
            'fontVariant': file.read(5).decode('utf-8').strip('\x00')
        }

        frames = []
        height = self.header['config']['charHeight']

        while True:
            try:
                if self.header['version'] == 3:
                    # Version 3: [8 bytes double timestamp] + [4 bytes frame_size]
                    timestamp, = struct.unpack('<d', file.read(8))
                    frame_size, = struct.unpack('<I', file.read(4))

                    # Next 'frame_size' bytes => 8-bit each
                    frame_data = file.read(frame_size)
                    if len(frame_data) < frame_size:
                        break  # incomplete read
                    # Convert bytes -> list of ints
                    frame_data = list(frame_data)

                    frames.append({
                        "timestamp": timestamp,
                        "frameNumber": None,
                        "frameSize": frame_size,
                        "frameContent": frame_data
                    })

                elif self.header['version'] == 2:
                    # Version 2: [4 bytes frame_number] + [4 bytes frame_size]
                    frame_number, frame_size = struct.unpack('<II', file.read(8))

                    raw_data = file.read(2 * frame_size)  # 16-bit each
                    if len(raw_data) < (2 * frame_size):
                        break  # incomplete read

                    # Convert each 2 bytes into a 16-bit
                    frame_data = []
                    for i in range(0, len(raw_data), 2):
                        val = struct.unpack('<H', raw_data[i:i + 2])[0]
                        frame_data.append(val)

                    # The original code rearranged column-by-column -> line-by-line
                    frame_data = [
                        frame_data[i * height + j]
                        for j in range(height)
                        for i in range(len(frame_data) // height)
                    ]

                    frames.append({
                        "timestamp": None,
                        "frameNumber": frame_number,
                        "frameSize": frame_size,
                        "frameContent": frame_data
                    })

                else:
                    # Unsupported version
                    print(f"Unsupported version: {self.header['version']}")
                    break

            except (struct.error, EOFError):
                break  # End of file or incomplete data

        self.frame_data = pd.DataFrame(frames)

    def print_info(self):
        print("Header Information:")
        for key, val in self.header.items():
            print(f"  {key}: {val}")

        print("\nFrame Data Summary:")
        print(f"Total Frames: {self.get_frame_count()}")
        print(f"Duration: {self.get_duration()} seconds")
        print(f"Frame Rate: {self.calculate_frame_rate()} fps")

    def get_data(self):
        """Return the frame data as a DataFrame for external processing."""
        return self.frame_data

    def generate_pseudo_frames(self, frame_rate):
        """Generate timestamps or frame numbers if they're missing, based on the frame_rate."""
        self.frame_rate = frame_rate
        if "timestamp" in self.frame_data.columns and self.frame_data["timestamp"].isnull().all():
            # No timestamps, but we do have frameNumbers
            if "frameNumber" in self.frame_data.columns and not self.frame_data["frameNumber"].isnull().all():
                self.frame_data["timestamp"] = self.frame_data["frameNumber"] / frame_rate

        elif "frameNumber" in self.frame_data.columns and self.frame_data["frameNumber"].isnull().all():
            # We have timestamps but no frameNumbers
            if "timestamp" in self.frame_data.columns and not self.frame_data["timestamp"].isnull().all():
                self.frame_data["frameNumber"] = (self.frame_data["timestamp"] * frame_rate).astype(int)

    def print_frame(self, frame_index):
        try:
            frame = self.frame_data.iloc[frame_index]
            content = frame["frameContent"]
            print(f"\nFrame {frame_index}:")
            for idx, value in enumerate(content):
                # Print 16-bit or 8-bit in hex with enough padding
                # If it's a 16-bit from DJO3, it might be up to 0xFFFF
                print(f"{value:04X}", end=" ")
                if (idx + 1) % 16 == 0:
                    print()
            print()
        except IndexError:
            print("Frame index out of bounds.")

    def calculate_frame_rate(self):
        """
        If we have timestamps in the DataFrame, we can attempt to compute a frame rate.
        """
        if "timestamp" in self.frame_data.columns and not self.frame_data["timestamp"].isnull().all():
            timestamps = self.frame_data["timestamp"].dropna()
            if len(timestamps) > 1:
                diffs = timestamps.diff().dropna()
                avg_dt = diffs.mean()
                if avg_dt > 0:
                    self.frame_rate = 1.0 / avg_dt
        return self.frame_rate

    def get_frame_count(self):
        return len(self.frame_data)

    def get_duration(self):
        """
        If we have timestamps, the duration is the max timestamp;
        otherwise approximate from frame_count / frame_rate.
        """
        if "timestamp" in self.frame_data.columns and not self.frame_data["timestamp"].isnull().all():
            self.duration = self.frame_data["timestamp"].max()
        elif self.frame_rate:
            self.duration = self.get_frame_count() / self.frame_rate
        return self.duration

    def statistics(self):
        print("OSD File Statistics:")
        print(f"Total Frames: {self.get_frame_count()}")
        print(f"Duration: {self.get_duration()} seconds")
        print(f"Frame Rate: {self.calculate_frame_rate()} fps")

    def parse(self, field_definitions):
        """
        Optional parse method. It attempts to find fields in the frame content by
        either an identifier or coordinates, with a certain length and format_type.
        """
        self.parsed_data_df = pd.DataFrame(index=self.frame_data.index, columns=field_definitions.keys())

        for frame_index, frame in self.frame_data.iterrows():
            frame_content = frame["frameContent"]

            for field_name, (identifier, coordinates, length, format_type) in field_definitions.items():
                try:
                    start_pos = None
                    if identifier != -1:
                        start_pos = self._find_identifier_in_grid(frame_content, identifier)
                        if start_pos is None:
                            continue
                        start_pos += 1 if length > 0 else -1
                    elif coordinates != [-1, -1]:
                        x, y = coordinates
                        char_width = self.header['config'].get('charWidth', 0)
                        start_pos = (y * char_width) + x
                    else:
                        continue

                    if length < 0:
                        start_pos += length
                    read_len = abs(length)

                    if start_pos < 0 or (start_pos + read_len) > len(frame_content):
                        raise IndexError("Reading beyond frame bounds")

                    data_slice = frame_content[start_pos:start_pos + read_len]

                    # Convert to a hex string
                    if isinstance(data_slice[0], int):
                        # data_slice is a list of int
                        data_hex = ''.join(f"{byte:02X}" for byte in data_slice)
                    else:
                        # If it's already bytes
                        data_hex = data_slice.hex()

                    # Interpret based on format_type
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

                    self.parsed_data_df.at[frame_index, field_name] = parsed_value

                except (IndexError, ValueError) as e:
                    print(f"Error parsing field '{field_name}' in frame {frame_index}: {e}")
                    continue

    def _find_identifier_in_grid(self, frame_content, identifier):
        """
        Attempts to find the first occurrence of `identifier` in frame_content.
        Works for the older 8-bit structure or 16-bit if the identifier is a 16-bit value.
        For DJO3 data, if the identifier is > 255, you might need to handle it differently.
        """
        try:
            return frame_content.index(identifier)
        except ValueError:
            return None

    @staticmethod
    def open_file_dialog():
        root = tk.Tk()
        root.withdraw()  # Hide the main window

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
