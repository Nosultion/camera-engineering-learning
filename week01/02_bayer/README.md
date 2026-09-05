# Week 01 实验：Bayer RAW / RAW10 Packing

> 从"理解 Camera Pipeline"进入"真正理解 Sensor 输出的 RAW/Bayer 数据"。
> 本目录全部实验基于 `input/input.jpg`（1702×1276）完成。

## 问题

> **一个 Bayer RAW Sensor 到底输出了什么？**

答案不是"一张 RGB 图片"，而是一条单通道的字节流：

```text
光 → Lens → Pixel Array → Color Filter (Bayer) → ADC → RAW10 → MIPI CSI-2 → SoC
```

- 每个像素位置只采样 **R / G / B 中的一种**（由 CFA 决定）
- ADC 把模拟电压量化成数字，常见 **10 bit**（RAW10）
- 数据在 MIPI CSI-2 上以 **packed 字节流** 传输

## 关键数字：1920×1080 Sensor 输出多少数据？

- 像素总数：1920 × 1080 = **2,073,600**
- 但它**不是** 2,073,600 × 3 个采样值 —— 每个像素只有 1 个采样值（R 或 G 或 B）
- RAW10 packed：2,073,600 × 10 bit = **约 2.47 MB/帧**
- 30 fps：约 **74 MB/s** 的字节流从 Sensor 流出

这就是 Bayer 的核心：**用一个采样值代替三个**，数据量降到 1/3，代价是颜色信息要靠后面的 ISP（Demosaic）重建。

## Bayer 的四种排列与 OpenCV 枚举

| 业界命名（第一行） | 2×2 单元 | OpenCV 枚举（BGR 输出） |
| --- | --- | --- |
| RGGB | `R G / G B` | `COLOR_BayerBG2BGR` |
| BGGR | `B G / G R` | `COLOR_BayerRG2BGR` |
| GBRG | `G B / R G` | `COLOR_BayerGR2BGR` |
| GRBG | `G R / B G` | `COLOR_BayerGB2BGR` |

⚠️ **OpenCV 的命名是个大坑**：`COLOR_BayerXX` 中的两个字母不是取"第一行"，
而是取**第二行的第 2、3 列**（见 [OpenCV 文档](https://docs.opencv.org/4.x/d8/d01/group__imgproc__color__conversions.html)）。
所以业界叫 RGGB 的模式，OpenCV 里叫 `BayerBG`。
本实验实测：用错枚举（`COLOR_BayerRG2BGR` 转 RGGB 数据）会导致 **R/B 互换**，PSNR 从 33 dB 掉到 20 dB。

参考：[OpenCV Color conversions — Bayer demosaicing](https://docs.opencv.org/4.x/d8/d01/group__imgproc__color__conversions.html)

## RAW8 / RAW10 / RAW12

| 格式 | 每像素 bit | 数值范围 | 未打包存储 | packed 存储 |
| --- | --- | --- | --- | --- |
| RAW8 | 8 | 0 ~ 255 | 1.00 B/px | - |
| RAW10 | 10 | 0 ~ 1023 | 2.00 B/px (uint16, 浪费 6 bit) | 1.25 B/px |
| RAW12 | 12 | 0 ~ 4095 | 2.00 B/px (uint16, 浪费 4 bit) | 1.50 B/px |

---

## 实验 1：RGB → Bayer RGGB（generate_bayer.py）

**原理**：模拟 CFA 的作用 —— 从 RGB 三通道图里按 RGGB 位置各取一个通道，拼成单通道图。

```text
(偶数行, 偶数列) → R      (偶数行, 奇数列) → G
(奇数行, 偶数列) → G      (奇数行, 奇数列) → B
```

**结果**（1702×1276）：

```text
RGB   : 1702×1276 × 3 bytes = 6,515,256 bytes
Bayer : 1702×1276 × 1 byte  = 2,171,752 bytes  ← 减少到 1/3
```

输出：`output/bayer_rggb.png`（单通道）+ `output/bayer_{r,gr,gb,b}.png`（4 个分通道图，未采样位置为黑，可以直观看到每个通道只"看到"一半/四分之一的像素）。

## 实验 2：8-bit → RAW10 模拟（generate_raw10.py）

**原理**：把 0~255 的 8-bit 数据 ×4，映射到 0~1023，模拟 RAW10 的取值范围。

⚠️ **重要**：这是**模拟**，不是真实 Sensor 的 RAW10 生成方式。
真实 Sensor 的 ADC 是直接对模拟电压做 10-bit 量化，不存在"先 8-bit 再乘 4"这一步。
这个实验只是为了理解 RAW10 的**数据范围**和**存储开销**。

**结果**：

```text
128 (8-bit) → 512 (10-bit)
RAW10 未打包 (uint16) : 4,343,504 bytes (2.00 B/px) ← 浪费 6 bit/像素
RAW10 packed 理论值   : 2,714,690 bytes (1.25 B/px)
```

输出：`output/raw10_unpacked.png`（16-bit PNG 容器）+ `output/bayer_raw10.raw`（uint16 little-endian 裸字节流，模拟 Sensor 直接吐出的数据），并读回验证一致。

## 实验 3：RAW10 Packing / Unpacking（raw10_packing.py）⭐

**为什么需要 packing**：RAW10 用 uint16 存会浪费 6 bit/像素。MIPI CSI-2 上的真实做法是：

```text
4 pixels × 10 bit = 40 bit = 5 bytes
```

**MIPI RAW10 packed 字节布局**：

```text
byte0 = P0[9:2]    byte1 = P1[9:2]    byte2 = P2[9:2]    byte3 = P3[9:2]
byte4 = P3[1:0] << 6 | P2[1:0] << 4 | P1[1:0] << 2 | P0[1:0]
```

手算示例（代码里已断言验证）：

```text
pixels [1023, 0, 682, 341] → FF 00 AA 55 63
```

**测试结果**（全部通过）：

```text
✅ 边界值 (0 / 1023) round-trip
✅ 0~1023 全值域（打乱顺序）round-trip：unpack(pack(x)) == x
✅ vectorized 版与 scalar 版逐字节一致
✅ 整幅图 round-trip：数据完全一致
```

**数据量**：4,343,504 bytes (2.00 B/px) → **2,717,880 bytes (1.25 B/px)**，节省 37.5%。

> 细节：理论值是 2,714,690 bytes，实际多出 3,190 bytes，
> 因为行宽 1702 不是 4 的倍数，打包时每行补到 1704（真实 Sensor 的 line width 也会按 MIPI 要求做对齐填充）。

输出：`output/bayer_raw10_packed.raw`

### 以后看到 `MEDIA_BUS_FMT_SRGGB10_1X10` 就知道它是什么了

```text
SRGGB10
   │
   ├── S    → Sensor（对比 M 开头表示 Memory）
   ├── RGGB → Bayer 排列
   └── 10   → 10 bit
```

而 `1X10` 表示 MIPI / media bus 上每像素对应 **1 个 10-bit word** —— 就是本实验实现的 packed 传输格式。

## 实验 4：Bayer → Demosaic → RGB（demosaic.py）

**流程**：`input.jpg → RGB → Bayer RGGB → Demosaic → RGB`

- 方案 A：手写 **Nearest Neighbor**（最近邻）—— 缺失通道从最近的采样点直接"借"值
- 方案 B：**OpenCV** `cv2.cvtColor(bayer, COLOR_BayerBG2BGR)`

**结果**（PSNR，越高越接近原图）：

| 方法 | PSNR |
| --- | --- |
| Nearest Neighbor（手写） | 28.54 dB |
| OpenCV（默认） | 33.04 dB |
| OpenCV VNG（对比参考） | 38.07 dB |

结论：最近邻简单、可解释，但质量明显差（锯齿/伪色）；OpenCV 的边缘感知插值明显更好 —— 这正是"ISP 里 Demosaic 为什么要做复杂插值"的最直观证据。

输出：`output/demosaic_nearest.png`、`output/demosaic_opencv.png`、`output/compare.png`（三图并排对比）、`output/diff_nearest.png` / `output/diff_opencv.png`（误差 ×20 放大图）、`output/crop_compare.png`（细节最丰富区域 2× 放大对比）。

## RAW 与 ISP 的连接

今天的实验把"ISP 的输入是什么"这个问题落到了字节层面：

```text
ISP 输入  = Bayer RAW（单通道、每像素 1 个采样值、RAW10 通常 packed）
ISP 输出  = RGB / YUV（三通道、可直接显示）
```

在 NVIDIA Jetson 的软件架构里（[Camera Software Development Solution](https://docs.nvidia.com/jetson/archives/r36.4/DeveloperGuide/SD/CameraDevelopment/CameraSoftwareDevelopmentSolution.html)）：

```text
CSI Camera ──┬── libargus + nvarguscamerasrc（走 Jetson ISP）
             └── v4l2src（不走 Jetson ISP 的 CSI Camera / USB Camera）
```

- **libargus**：Jetson 的相机应用框架，走 Jetson ISP 的标准路径
- **nvarguscamerasrc**：GStreamer 里对应的 source 插件
- **v4l2src**：V4L2 路径（[NVIDIA V4L2 文档](https://docs.nvidia.com/jetson/archives/r36.2/DeveloperGuide/SD/CameraDevelopment.html) 里就有用 `v4l2-ctl` 直接抓 Sensor Bayer RAW 的例子）

**现在只需要认识这些名字**，第 20~21 周再深入。没有 Camera Data Model 之前去啃 LibArgus 会事倍功半。

## 踩过的坑

1. **OpenCV Bayer 枚举命名**：`COLOR_BayerRG2BGR` 并不对应"第一行是 R G"的 RGGB！
   OpenCV 按第二行第 2、3 列命名，RGGB 数据要用 `COLOR_BayerBG2BGR`。
   用错的表现很隐蔽：G 通道完全正常，R/B 互换，PSNR 从 33 dB 掉到 20 dB。
2. **行宽对齐**：packing 前要把行宽补到 4 的倍数（1702 → 1704），否则最后一组不满 4 个像素无法打包。
3. **16-bit PNG 是"人看"的容器，不是 Sensor 的真实输出**：真实 Sensor 输出的是没有文件头的裸字节流，分辨率等信息由驱动配置告知接收端。

## 学习问答（复习用）

> 记录学习过程中提问过的问题和答案，方便复习回顾。

### Q1：为什么 `cv2.imread` 读进来是 BGR 而不是 RGB？

- **历史原因**：OpenCV 诞生于 2000 年前后的 Windows 生态——BMP 文件、GDI 的 `COLORREF`（0x00BBGGRR）、早期相机驱动输出都是 BGR 顺序，OpenCV 顺势把内存字节序定为 BGR
- **内存层面无所谓对错**：图像就是一堆字节，BGR/RGB 只是"解释方式"；`cvtColor(COLOR_BGR2RGB)` 只调换通道位置，几乎零成本
- **为什么一直不改**：几十亿行代码依赖此约定，`imshow` / `imwrite` / 所有 `COLOR_*` 枚举都按 BGR 解释，改动的破坏性远大于收益
- **口诀**：OpenCV 内部全是 BGR；数据交给 matplotlib / PIL / 自己的 RGB 约定前，先 `cvtColor` 一次

### Q2：`imread` 和 `cvtColor(BGR2RGB)` 两行分别做什么？

| 行 | 做的事 | 结果 |
| --- | --- | --- |
| `cv2.imread(path, IMREAD_COLOR)` | 解码文件 → 内存 numpy 数组 | (H, W, 3) uint8，**BGR 顺序** |
| `cv2.cvtColor(img, COLOR_BGR2RGB)` | 调换每个像素的第 0/2 通道 | 顺序变 **RGB**，像素数值不变 |

- 真实像素示例：`[235, 188, 191]` (B,G,R) → `[191, 188, 235]` (R,G,B)，中间的 G 不动
- 为什么需要第二行：`rgb_to_bayer_rggb` 里约定"通道 0 = R"，不转就会 R/B 互换——就是踩过的第一个坑

### Q3：`IMREAD_COLOR_BGR` 和 `IMREAD_COLOR` 有区别吗？

- **没有**，是同一个值（= 1）的同义词，OpenCV 4.5.3 起加的别名，纯为可读性
- **真正有区别的是 `IMREAD_COLOR_RGB`**：直接读成 RGB，可省掉 cvtColor。
  注意 OpenCV 5 里它的值是 256（4.x 里是 4，跨大版本变了值，勿硬编码数字）
- 底层仍是"解码成 BGR 再换通道"，不是性能优化；数组变成 RGB 后，`imshow`/`imwrite` 依旧按 BGR 解释

### Q4：生成 Bayer 的 4 行切片代码是什么原理？

两层理解：

- **numpy 切片**：`0::2` 取偶数索引（0,2,4...），`1::2` 取奇数索引（1,3,5...）。
  行×列两种取法 = 4 种组合，把整图划分成 4 个互补的"棋盘格"，每个像素恰好属于其中一个
- **Bayer 物理原理**：CFA 以 2×2 单元（R G / G B）周期性平铺整个传感器：
  (偶,偶) 位置全盖 R 滤光片、(偶,奇)/(奇,偶) 盖 G、(奇,奇) 盖 B。
  4 个切片正是在模拟这 4 种滤光片对整张图的选择
- 每个位置只保留一个通道值，其余两个分量被**物理丢弃** → 3 bytes/px 变 1 byte/px
- **G 出现两次（Gr/Gb）**：人眼对绿色最敏感，G 采样率翻倍；真实 Sensor 中两者可能有 green imbalance，ISP 需要专门校正

### Q5：为什么 4 张分通道图看起来区别不大？

- **黑棋盘格稀释**：每张图 3/4 是纯黑，缩小显示时被平均掉，看到的只剩"场景明暗轮廓"，而轮廓四张图共享
- **低饱和图片**：本图 R/G/B 采样均值 116 / 110 / 103，平均 |R-B| 只有 22.5（最大 255）——本来就接近灰色照片
- **gr 与 gb 本来就是同一颜色**（都是 G），只是采样位置错开一个像素
- 像素级其实不同：同一区域 R 存 191、G 存 188、B 存 235；100% 放大看棋盘格相位，或用高饱和色块图才能直观看出差异

### Q6：`cv2.IMREAD_UNCHANGED` 的作用？

- 值 = -1，含义：**不做任何显示用转换，原样保留**——位深（16-bit 保持 16-bit）、通道数（含 alpha）
- 对比实测（16-bit PNG 存 512）：`UNCHANGED` → uint16 的 `512`；`COLOR`/`GRAYSCALE` → uint8 的 `2`！
  因为 OpenCV 16→8 是**取高字节（v>>8）**而不是等比缩放，255 会直接变成 0
- `raw10_packing.py` 必须用它：round-trip 测试要操作真实的 0~1023 值；
  错用 `IMREAD_COLOR` 会让数据先被毁掉，**而且测试照样通过**——隐蔽的假结果
- 适用：16/32-bit 深度图、带 alpha 的 PNG、任何需要精确数值的场景
- 顺带：`IMREAD_ANYDEPTH`（= 2）也保留位深，但强制转 3 通道 BGR

### Q7：为什么 compare.png 三张图看不出区别？

- **误差低于视觉阈值**：PSNR 28.5 / 33 dB → 实测平均误差仅 6.9 / 4.1 灰度级，人眼感知阈值约 1~3%
- **误差集中在高频**：平滑区域几乎无误差，误差在边缘/纹理处（误差>10 的像素占比 18.9% vs 10.5%），人眼不逐像素检查纹理
- **缩小显示又平均一层**：三图并排缩略显示，误差被下采样平均掉
- **实验对 Demosaic 太友好**：Bayer 从原图直接采样，无噪声、无镜头模糊，且本图低饱和（伪色不明显）
- 怎么看差异：`output/diff_nearest.png` / `diff_opencv.png`（误差 ×20 放大，越亮误差越大）、`output/crop_compare.png`（细节区域 2× 放大，Nearest 在边缘有 zipper 锯齿）
- 引申结论：图像质量不能靠眼睛，要靠 PSNR 等客观指标（Week 12 展开）

### Q8：PSNR 全称是什么？代表什么含义？

- 全称 **Peak Signal-to-Noise Ratio（峰值信噪比）**
- 公式：`PSNR = 10 × log10(MAX² / MSE)`，MAX = 255（8-bit），MSE = 平均平方误差
- 含义：把重建误差当作"噪声"，衡量"最大信号是噪声的多少倍"；Peak 指用固定的最大可能值（255），与图像内容无关；取对数是把误差的数量级范围压缩到好读的 dB 刻度
- 换算直觉：**每 20 dB ≈ RMSE 差 10 倍，每 6 dB ≈ 差 2 倍**；
  28.54 dB → RMSE≈9.5，33.04 dB → RMSE≈5.7
- 分级参考：>40 dB 极好 / 30~40 好 / 20~30 差 / <20 很差
- 局限：逐像素计算、不懂结构（整体平移 1 像素人眼无感，PSNR 却暴跌）；感知型指标（SSIM 等）留到 Week 12

## 结论

- Bayer RAW Sensor 输出的本质：**每个像素 1 个采样值的单通道数据**（RAW10 = 0~1023）
- RAW10 在 MIPI 上以 **4 像素 → 5 字节** 的 packed 形式传输
- Bayer 只是"半成品"，必须经过 Demosaic（ISP 的一部分）才能恢复 RGB —— 恢复是有损的（PSNR 28~38 dB）
- 下一步：MIPI CSI-2 + RAW 数据如何从 Sensor 进入 SoC（Lane / Virtual Channel / Frame Start / Line Start）→ **已完成，见 [`03_mipi_csi2/`](../03_mipi_csi2/)**

## 运行方式

```bash
python generate_bayer.py      # 实验 1: RGB → Bayer
python generate_raw10.py      # 实验 2: RAW10 模拟
python raw10_packing.py       # 实验 3: RAW10 packing (含全部测试)
python demosaic.py            # 实验 4: Demosaic 对比
```
