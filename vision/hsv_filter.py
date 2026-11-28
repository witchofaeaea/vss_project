
import cv2
import numpy as np

LOWER_RED1 = np.array([0, 150, 150])
UPPER_RED1 = np.array([8, 255, 255])

LOWER_RED2 = np.array([172, 150, 150])
UPPER_RED2 = np.array([180, 255, 255])


def create_red_laser_mask(frame: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    mask1 = cv2.inRange(hsv, LOWER_RED1, UPPER_RED1)
    mask2 = cv2.inRange(hsv, LOWER_RED2, UPPER_RED2)

    return cv2.bitwise_or(mask1, mask2)
