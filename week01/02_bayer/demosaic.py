"""实验 4：Bayer → Demosaic → RGB

流程：
    input.jpg → RGB → Bayer RGGB → Demosaic → RGB

方案 A：手写 Nearest Neighbor（最近邻）Demosaic
  每个像素缺失的两个通道，从最近的采样点直接"借"值。
  质量差（会有锯齿/伪色），但能讲清楚 Demosaic 在解决什么问题。

方案 B：OpenCV cv2.cvtColor(..., COLOR_BayerRG2BGR)
  OpenCV 默认的 Bayer 插值算法（边缘感知，比最近邻好得多）。

最后对比：Original vs Nearest vs OpenCV，并计算 PSNR。

用法：
    python demosaic.py
"""

from pathlib import Path

import cv2
import numpy as np

from generate_bayer import rgb_to_bayer_rggb

HERE = Path(__file__).resolve().parent
INPUT_DIR = HERE / "input"
OUTPUT_DIR = HERE / "output"


def demosaic_nearest(bayer: np.ndarray) -> np.ndarray:
    """手写最近邻 Demosaic。

    思路：Bayer 每个位置只采了一种颜色，另外两种颜色
    从"距离最近的采样点"直接复制。

    实现细节：
    1. 用对称填充扩一圈，避免边界越界
    2. 原图坐标 (i, j) 在填充图中位于 (r, c) = (i+1, j+1)
       填充图中：R 在 (奇, 奇)，B 在 (偶, 偶)，G 在 (偶, 奇)/(奇, 偶)
    3. R/B：把行列坐标"吸附"到最近的采样位置
    4. G：像素本身是 G 位置就取自己，否则取上/右最近的 G
    """
    h, w = bayer.shape
    padded = np.pad(bayer, 1, mode="symmetric")

    i = np.arange(h)          # 原图行坐标
    j = np.arange(w)          # 原图列坐标
    r = i + 1                 # 填充图行坐标
    c = j + 1                 # 填充图列坐标

    # R: 最近的 (奇, 奇)
    r_odd = (r - 1) // 2 * 2 + 1
    c_odd = (c - 1) // 2 * 2 + 1
    R = padded[r_odd][:, c_odd]

    # B: 最近的 (偶, 偶)
    r_even = r // 2 * 2
    c_even = c // 2 * 2
    B = padded[r_even][:, c_even]

    # G: G 位置取自己；R/B 位置取上方的 G
    is_g_pos = ((r % 2 == 0)[:, None] & (c % 2 == 1)[None, :]) \
             | ((r % 2 == 1)[:, None] & (c % 2 == 0)[None, :])
    G = np.where(is_g_pos, padded[1:-1, 1:-1], padded[r_even][:, c_even + 1])

    return np.stack([R, G, B], axis=-1).astype(np.uint8)


def psnr(a: np.ndarray, b: np.ndarray) -> float:
    """峰值信噪比（越大越接近原图）。"""
    mse = ((a.astype(np.float64) - b.astype(np.float64)) ** 2).mean()
    return float(10 * np.log10(255.0 ** 2 / mse)) if mse > 0 else float("inf")


def make_compare(images, labels) -> np.ndarray:
    """横向拼接 + 顶部标签，方便一眼对比。"""
    w = images[0].shape[1]
    canvas = np.hstack(images)
    for k, label in enumerate(labels):
        cv2.putText(canvas, label, (k * w + 12, 36),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
    return canvas


def main() -> None:
    src = INPUT_DIR / "input.jpg"
    rgb = cv2.imread(str(src), cv2.IMREAD_COLOR)
    rgb = cv2.cvtColor(rgb, cv2.COLOR_BGR2RGB)
    print(f"输入: {src}  {rgb.shape[1]}x{rgb.shape[0]}")

    # RGB → Bayer
    bayer = rgb_to_bayer_rggb(rgb)

    # 方案 A: 手写最近邻
    nearest = demosaic_nearest(bayer)

    # 方案 B: OpenCV
    # 注意：OpenCV 的枚举不是按"第一行"命名的！
    # COLOR_BayerXX 中的两个字母取自第二行的第 2、3 列，
    # 所以业界叫 RGGB 的模式（第一行 R G），OpenCV 里是 COLOR_BayerBG2BGR。
    # 若错用 COLOR_BayerRG2BGR，R/B 会互换（本实验实测 PSNR 从 33 dB 掉到 20 dB）。
    opencv_rgb = cv2.cvtColor(bayer, cv2.COLOR_BayerBG2BGR)
    opencv_rgb = cv2.cvtColor(opencv_rgb, cv2.COLOR_BGR2RGB)

    # 评价
    print(f"PSNR 最近邻 : {psnr(rgb, nearest):.2f} dB")
    print(f"PSNR OpenCV : {psnr(rgb, opencv_rgb):.2f} dB")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUTPUT_DIR / "demosaic_nearest.png"),
                cv2.cvtColor(nearest, cv2.COLOR_RGB2BGR))
    cv2.imwrite(str(OUTPUT_DIR / "demosaic_opencv.png"),
                cv2.cvtColor(opencv_rgb, cv2.COLOR_RGB2BGR))

    compare = make_compare([rgb, nearest, opencv_rgb],
                           ["Original", "Nearest Neighbor", "OpenCV"])
    cv2.imwrite(str(OUTPUT_DIR / "compare.png"),
                cv2.cvtColor(compare, cv2.COLOR_RGB2BGR))
    print("已保存: output/demosaic_nearest.png")
    print("已保存: output/demosaic_opencv.png")
    print("已保存: output/compare.png (Original / Nearest / OpenCV 对比)")


if __name__ == "__main__":
    main()
