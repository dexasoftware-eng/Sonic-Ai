import pytest
import numpy as np
from src.audio.augmentor import AudioAugmentor

@pytest.fixture
def augmentor():
    return AudioAugmentor(sample_rate=16000)

@pytest.fixture
def sample_sine():
    t = np.linspace(0, 2.0, 32000, endpoint=False)
    # 440 Hz test tone
    audio = 0.5 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    return audio

def test_pitch_shift(augmentor, sample_sine):
    shifted = augmentor.pitch_shift(sample_sine, n_semitones=2.0)
    assert len(shifted) == len(sample_sine)
    assert shifted.dtype == np.float32
    assert not np.allclose(shifted, sample_sine)

def test_time_stretch(augmentor, sample_sine):
    stretched = augmentor.time_stretch(sample_sine, rate=1.1)
    assert len(stretched) == len(sample_sine)
    assert stretched.dtype == np.float32

def test_inject_noise(augmentor, sample_sine):
    noisy = augmentor.inject_noise(sample_sine, snr_db=15.0)
    assert len(noisy) == len(sample_sine)
    assert np.max(np.abs(noisy)) <= 0.99
    assert not np.allclose(noisy, sample_sine)

def test_scale_gain(augmentor, sample_sine):
    scaled = augmentor.scale_gain(sample_sine, factor=0.7)
    assert len(scaled) == len(sample_sine)
    assert np.max(np.abs(scaled)) < np.max(np.abs(sample_sine))

def test_generate_variations(augmentor, sample_sine):
    variations = augmentor.generate_variations(sample_sine, count=5)
    assert len(variations) == 5
    for var in variations:
        assert len(var) == len(sample_sine)
        assert np.max(np.abs(var)) <= 0.99
