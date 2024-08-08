import logging
from typing import Optional

from .executor import AbstractTextToSpeech, TextToSpeechExecutor, TextToSpeechOverrideBehavior
from .google_cloud_engine import GoogleCloudTextToSpeech
from .gtts_engine import GTTSTextToSpeech
from .pyttsx3_engine import PyTTSx3TextToSpeech


def get_text_to_speech(name: str) -> AbstractTextToSpeech:
    """
    Get the text-to-speech engine by name.

    Parameters
    ----------
    name : str
        The name of the text-to-speech engine.
    logger : logging.Logger, optional
        The logger to use, by default DEFAULT_LOGGER

    Returns
    -------
    AbstractTextToSpeech
        The text-to-speech engine.
    """
    name = name.lower()
    if name == "google":
        return GoogleCloudTextToSpeech()
    if name == "gtts":
        return GTTSTextToSpeech()
    if name == "pyttsx3":
        return PyTTSx3TextToSpeech()
    raise ValueError(f"Unsupported text-to-speech engine: {name}")