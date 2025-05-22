import struct

def build_wav_header(num_channels, sample_rate, bits_per_sample):
    """
    Constroi um cabeçalho WAV com tamanho dummy para streaming.
    Os campos de tamanho ficam com valor 0, pois o tamanho total é desconhecido.
    """
    data_size = 0  # Tamanho dummy; pode ser 0 ou 0xFFFFFFFF, se necessário
    file_size = 36 + data_size  # Tamanho total - 8 (dummy)
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',                                            # ChunkID
        file_size,                                          # ChunkSize
        b'WAVE',                                            # Format
        b'fmt ',                                            # Subchunk1ID
        16,                                                 # Subchunk1Size (PCM)
        1,                                                  # AudioFormat (1 = PCM)
        num_channels,                                       # NumChannels
        sample_rate,                                        # SampleRate
        sample_rate * num_channels * bits_per_sample // 8,  # ByteRate
        num_channels * bits_per_sample // 8,                # BlockAlign
        bits_per_sample,                                    # BitsPerSample
        b'data',                                            # Subchunk2ID
        data_size                                           # Subchunk2Size (dummy)
    )
    
    return header
