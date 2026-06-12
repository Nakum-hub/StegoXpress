"""
AudioEngine — hide data in 16-bit PCM WAV files using LSB of each sample's low byte.
Uses Python's built-in wave module only — no external audio dependencies.
"""
import struct
import wave


class AudioEngine:

    @staticmethod
    def encode(wav_path: str, payload: bytes, output_path: str) -> None:
        with wave.open(wav_path, "rb") as wav:
            params = wav.getparams()
            if params.sampwidth != 2:
                raise ValueError(
                    f"Only 16-bit PCM WAV supported (sampwidth=2). "
                    f"Got sampwidth={params.sampwidth}"
                )
            frames = wav.readframes(params.nframes)

        full_data = struct.pack(">I", len(payload)) + payload
        bits_needed = len(full_data) * 8
        # Each 16-bit sample contributes 1 LSB (2 bytes per sample for each channel)
        n_samples = len(frames) // params.sampwidth
        capacity_bits = n_samples  # 1 bit per 16-bit sample

        if bits_needed > capacity_bits:
            raise ValueError(
                f"WAV too short for payload: needs {bits_needed} bits, "
                f"have {capacity_bits} bits ({n_samples} samples)"
            )

        frame_bytes = bytearray(frames)
        bits = [(b >> i) & 1 for b in full_data for i in range(7, -1, -1)]

        bit_pos = 0
        sample_idx = 0
        while bit_pos < len(bits) and sample_idx < n_samples:
            # Low byte index of sample (little-endian 16-bit: low byte first)
            byte_idx = sample_idx * params.sampwidth
            frame_bytes[byte_idx] = (frame_bytes[byte_idx] & 0xFE) | bits[bit_pos]
            bit_pos += 1
            sample_idx += 1

        with wave.open(output_path, "wb") as out:
            out.setparams(params)
            out.writeframes(bytes(frame_bytes))

    @staticmethod
    def decode(wav_path: str) -> bytes:
        with wave.open(wav_path, "rb") as wav:
            params = wav.getparams()
            if params.sampwidth != 2:
                raise ValueError("Only 16-bit PCM WAV supported")
            frames = wav.readframes(params.nframes)

        frame_bytes = bytearray(frames)
        n_samples = len(frame_bytes) // params.sampwidth

        bits = []
        for sample_idx in range(n_samples):
            byte_idx = sample_idx * params.sampwidth
            bits.append(frame_bytes[byte_idx] & 1)

        length = 0
        for b in bits[:32]:
            length = (length << 1) | b

        needed_bits = 32 + length * 8
        if needed_bits > len(bits):
            raise ValueError("WAV does not contain enough encoded data")

        data = bytearray()
        for i in range(32, needed_bits, 8):
            byte = 0
            for b in bits[i:i + 8]:
                byte = (byte << 1) | b
            data.append(byte)

        return bytes(data)

    @staticmethod
    def capacity_bytes(wav_path: str) -> int:
        with wave.open(wav_path, "rb") as wav:
            params = wav.getparams()
        n_samples = params.nframes * params.nchannels
        return n_samples // 8 - 4
