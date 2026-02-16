"""Built-in generator registrations."""

from .fabric_1_21_11 import Fabric12111Generator
from .registry import register_generator

register_generator(Fabric12111Generator(), replace=True)

__all__ = ["Fabric12111Generator"]
