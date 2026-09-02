"""实验 1：RGB → Bayer (RGGB)

模拟 CFA（Color Filter Array）的作用：
一张普通的 3 通道 RGB 图片，经过 Bayer 滤波阵列后，
每个像素位置只保留 R / G / B 中的一种颜色，变成单通道图。

RGGB 排列规则（以 2x2 为一个重复单元）：

    (偶数行, 偶数列) → R
    (偶数行, 奇数列) → G   (Gr)
    (奇数行, 偶数列) → G   (Gb)
    (奇数行, 奇数列) → B

用法：
    python generate_bayer.py [输入图片]
默认输入：input/input.jpg
"""

import sys
from pathlib import Path

import cv2
import numpy as np
 
HERE = Path(__file__).resolve().parent
INPUT_DIR = HERE / "input"
OUTPUT_DIR = HERE / "output"


def rgb_to_bayer_rggb(rgb: np.ndarray) -> np.ndarray:
    """RGB 三通道图 → RGGB Bayer 单通道图。

    输入: rgb, shape (H, W, 3), uint8
    输出: bayer, shape (H, W), uint8
    """
    h, w = rgb.shape[:2]
    bayer = np.zeros((h, w), dtype=np.uint8)

    # 直接按 RGGB 位置从对应通道取值
    bayer[0::2, 0::2] = rgb[0::2, 0::2, 0]  # R
    bayer[0::2, 1::2] = rgb[0::2, 1::2, 1]  # Gr
    bayer[1::2, 0::2] = rgb[1::2, 0::2, 1]  # Gb
    bayer[1::2, 1::2] = rgb[1::2, 1::2, 2]  # B
    return bayer


def split_channels(bayer: np.ndarray):
    """把 Bayer 拆成 4 个子图（未采样的位置置 0），便于观察。"""
    h, w = bayer.shape
    r = np.zeros((h, w), dtype=np.uint8)
    gr = np.zeros((h, w), dtype=np.uint8)
    gb = np.zeros((h, w), dtype=np.uint8)
    b = np.zeros((h, w), dtype=np.uint8)
    r[0::2, 0::2] = bayer[0::2, 0::2]
    gr[0::2, 1::2] = bayer[0::2, 1::2]
    gb[1::2, 0::2] = bayer[1::2, 0::2]
    b[1::2, 1::2] = bayer[1::2, 1::2]
    return r, gr, gb, b


def print_bayer_layout(size: int = 8) -> None:
    """打印左上角 size×size 的 Bayer 布局示意（用字母表示颜色位置）。"""
    # 只关心位置属于哪个通道，不关心数值
    row_even = (np.arange(size)[:, None] % 2 == 0)  # shape (size,1)
    col_even = (np.arange(size)[None, :] % 2 == 0)  # shape (1,size)
    channel = np.where(
        row_even & col_even, "R",
        np.where(row_even, "G",
                 np.where(col_even, "G", "B")),
    )
    print(f"Bayer 布局（左上角 {size}x{size}）：")
    for row in channel:
        print("  " + " ".join(row))


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else INPUT_DIR / "input.jpg"
    print(f"输入图片: {src}")

    rgb = cv2.imread(str(src), cv2.IMREAD_COLOR)  # OpenCV 读进来是 BGR
    rgb = cv2.cvtColor(rgb, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    print(f"RGB 图: {w}x{h}, 3 通道, 每像素 3 bytes")

    bayer = rgb_to_bayer_rggb(rgb)
    print(f"Bayer 图: {w}x{h}, 1 通道, 每像素 1 byte")
    print(f"数据量: {w*h*3} bytes -> {w*h} bytes (减少到 1/3)")

    print_bayer_layout()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUTPUT_DIR / "bayer_rggb.png"), bayer)

    r, gr, gb, b = split_channels(bayer)
    for name, ch in (("r", r), ("gr", gr), ("gb", gb), ("b", b)):
        cv2.imwrite(str(OUTPUT_DIR / f"bayer_{name}.png"), ch)
    print("已保存: output/bayer_rggb.png")
    print("已保存: output/bayer_{r,gr,gb,b}.png (4 个分通道图, 未采样位置为黑)")


if __name__ == "__main__":
    main()
