"""HSV renk filtreleme modulu: Kirmizi lazer tespiti icin renk maskesi olusturur."""

from typing import Tuple
import cv2
import numpy as np

# Kirmizi lazer icin HSV renk araliklari (0-10 ve 170-180)
LOWER_RED1 = np.array([0, 100, 100])
UPPER_RED1 = np.array([10, 255, 255])

LOWER_RED2 = np.array([170, 100, 100])
UPPER_RED2 = np.array([180, 255, 255])


def create_red_laser_mask(frame: np.ndarray) -> np.ndarray:
    """BGR formatindaki kareyi HSV'ye cevirip kirmizi lazer maskesi dondurur."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, LOWER_RED1, UPPER_RED1)
    mask2 = cv2.inRange(hsv, LOWER_RED2, UPPER_RED2)
    return cv2.bitwise_or(mask1, mask2)
