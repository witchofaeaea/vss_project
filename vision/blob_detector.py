"""Lazer noktası tespiti: morfolojik gürültü temizleme, blob tespiti ve centroid çıkarımı."""
from typing import Optional, Tuple

import cv2
import numpy as np


def clean_mask(binary_mask: np.ndarray, kernel_size: int = 3, open_iter: int = 1, close_iter: int = 1) -> np.ndarray:
    """Morphological Opening (kucuk gürültü sil) + Closing (blob içindeki boşlukları kapat).

    Not: Lazer noktası cok küçükse (1-2 piksel) opening onu da silebilir.
    Bu durumda open_iter=0 verip gürültüyü min_area ile ele."""
    mask = binary_mask
    if mask.dtype != np.uint8:
        mask = (mask > 0).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    if open_iter > 0:
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=open_iter)
    if close_iter > 0:
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=close_iter)
    return mask


def extract_laser_centroid(
    binary_mask: Optional[np.ndarray],
    min_area: float = 2.0,
    max_area: float = 500.0,
    kernel_size: int = 3,
    open_iter: int = 1,
    close_iter: int = 1,
) -> Optional[Tuple[float, float]]:
    """Binary mask içinden lazer noktasinin (cx, cy) kutle merkezini dondurur.

    Alan aralığına uyan bloblardan en büyüğünü seç. Uygun blob yoksa None döndür.
    connectedComponentsWithStats sayesinde 1-2 pikselik blobların alanı
    (cv2.contourArea'nin aksine) 0 çıkmaz"""
    if binary_mask is None or binary_mask.size == 0 or not np.any(binary_mask):
        return None

    cleaned = clean_mask(binary_mask, kernel_size, open_iter, close_iter)

    count, _, stats, centroids = cv2.connectedComponentsWithStats(cleaned, connectivity=8)

    best_idx, best_area = None, -1
    for i in range(1, count):  # 0 = arka plan
        area = stats[i, cv2.CC_STAT_AREA]
        if min_area <= area <= max_area and area > best_area:
            best_idx, best_area = i, area

    if best_idx is None:
        return None

    cx, cy = centroids[best_idx]
    return float(cx), float(cy)
