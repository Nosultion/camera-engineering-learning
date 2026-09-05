# Week 01 实验：MIPI CSI-2 + Sensor RAW 如何进入 SoC

> Day 3：接上 Day 2 的 Bayer RAW10，回答"RAW 数据是怎么从 Sensor 到达 SoC 的"。

## 今天要回答的 5 个问题

1. Sensor 为什么需要 MIPI CSI-2？
2. MIPI CSI-2 的 Lane 是什么？
3. RAW10 是怎么通过 MIPI 传输的？
4. SoC 收到数据后，怎么知道"这一帧开始了 / 这一行开始了 / 这是 RAW10 / 这是第几个 Camera"？
5. V4L2 在这里处于什么位置？

## 数据流全景图（实验 3）

```text
             Camera Module
                  │
                  ↓
          ┌──────────────┐
          │ Image Sensor │
          └──────┬───────┘
                 │
             Bayer RAW10
                 │
                 ↓
          ┌──────────────┐
          │ MIPI CSI-2   │
          └──────┬───────┘
                 │
        ┌────────┴────────┐
        │   CSI Receiver  │
        └────────┬────────┘
                 │
                 ↓
               V4L2
                 │
                 ↓
                ISP
                 │
        ┌────────┴────────┐
        ↓                 ↓
       RGB               YUV
        │                 │
        └────────┬────────┘
                 ↓
             Application
```

每一层在做什么：

| 层 | 职责 | 对应知识 |
| --- | --- | --- |
| Image Sensor | 光电转换 + ADC，产生 Bayer RAW10 | Day 1 / Day 2 |
| MIPI CSI-2 | 把 RAW 按协议打包，高速串行发送 | **今天** |
| CSI Receiver | SoC 内的接收端，解出字节流写入内存（DMA） | **今天** |
| V4L2 | Linux 标准摄像头接口，向用户空间暴露 /dev/videoN | **今天** |
| ISP | RAW → RGB / YUV | Week 01 Day 4 起 |
| Application | 显示 / 编码 / 算法处理 | 后续 |

---

## ① Sensor 为什么需要 MIPI CSI-2？

**老方案：并行接口（DVP）**。每个像素周期的 8/10/12/16 个 bit 用等量的数据线并行传输，还要 PCLK + HSYNC + VSYNC：

```text
并行接口: 数据线 ×8~16 + PCLK + HSYNC + VSYNC ≈ 20 根线
  - 线多：PCB 走线、连接器、FPC 成本高
  - 速率受限：PCLK 到百 MHz 量级就上不去了（并行线间 skew 问题）
  - EMI：大量单端信号同时翻转
```

**MIPI CSI-2 的做法：高速串行差分**：

```text
MIPI CSI-2 (D-PHY): 1 对时钟差分线 + 1~4 对数据差分线
  - 每对差分线就是一个 Lane，走线数从 20+ 降到 4~10 根
  - 差分 + 低电压摆幅（HS 模式 ~200 mV）→ EMI 小、功耗低
  - 高速：D-PHY 每 lane 1.5~4.5 Gbps（按版本），DDR 双边沿采样
  - MIPI Alliance 统一标准 → 任意 Sensor 可对接任意 SoC 接收端
```

一句话：**CSI-2 是 Sensor 和 SoC 摄像头接收端之间的高速串行图像传输协议**，用最少的线传最多的数据。

## ② Lane 是什么？

Lane = **一对差分线构成的一条高速串行数据通道**。带宽和 lane 数成正比：

```text
1 Lane:  Sensor ────────────────→ SoC

2 Lane:  Sensor ──────┬─────────→ SoC
                      └─────────→

4 Lane:  Sensor ──┬───┬───┬─────→ SoC
                  │   │   │
```

D-PHY 各版本单 lane 速率上限：

| D-PHY 版本 | 单 lane 速率 |
| --- | --- |
| v1.1 | 1.5 Gbps |
| v1.2 | 2.5 Gbps |
| v2.0 | 4.5 Gbps |

**工程思维**：lane 数不是越多越好。lane 多 → 单 lane 速率可以降低（信号完整性更好、EMI 更小、FPC 可以更长），但引脚和功耗增加。实际是"数据率需求 ↔ 单 lane 速率 ↔ lane 数"的平衡，见实验 2。

## ③ RAW10 是怎么通过 MIPI 传输的？

MIPI CSI-2 不是"把字节一个接一个发过去"这么简单，它是**按包（Packet）**组织的：

```text
短包 Short Packet（4 字节）：同步用
  Byte0  Byte1  Byte2  Byte3
  ┌─────┬──────┬──────┬─────┐
  │ DI  │ 数据域(16bit) │ ECC │
  └─────┴──────┴──────┴─────┘

长包 Long Packet（图像数据用）：
  包头(4B) + 有效载荷(WC 字节) + CRC(2B)
  ┌─────┬──────┬──────┬─────┬───────────────────┬──────┐
  │ DI  │ Word Count  │ ECC │   Payload         │ CRC  │
  └─────┴──────┴──────┴─────┴───────────────────┴──────┘
```

- **DI（Data Identifier）**：1 字节 = VC(2 bit) + DT(6 bit)，告诉接收端"这一包是什么"
- **WC（Word Count）**：payload 字节数（16 bit）

**ECC 与 CRC 的分工**：

```text
ECC ──→ Header   错误检测 + 纠正（纠 1 bit 错 / 检 2 bit 错）
CRC ──→ Payload  错误检测（16 bit 校验，只检不纠）
```

| | 保护对象 | 能力 | 设计原因 |
| --- | --- | --- | --- |
| ECC | 包头 4 字节（DI + WC + ECC） | 检 2 bit / 纠 1 bit | 包头错了（尤其 WC）整个包的边界都无法解析，代价大 → 给纠错能力 |
| CRC | Payload（最长 65535 字节） | 检错 | Payload 出错只是坏掉少数像素，代价小 → 检测到后丢弃该包即可，省带宽 |

而长包的 payload 里放的，就是 **Day 2 实验实现的 packed RAW10**：

```text
4 像素 × 10 bit = 40 bit = 5 字节（见 02_bayer/raw10_packing.py）
```

也就是 MIPI 总账：**传感器线路上实际传输的 RAW10 就是 1.25 bytes/px 的 packed 字节流**。

## ④ SoC 怎么知道帧边界 / 格式 / 哪个相机？

全靠 DI 里的两个字段 + 协议规定的同步包：

### Data Type（DT，6 bit）—— 回答"这是不是 RAW10"

| DT | 含义 | DT | 含义 |
| --- | --- | --- | --- |
| 0x00 | Frame Start | 0x24 | RGB888 |
| 0x01 | Frame End | 0x2A | RAW8 |
| 0x02 | Line Start | **0x2B** | **RAW10** |
| 0x03 | Line End | 0x2C | RAW12 |
| 0x1E | YUV422 8-bit | 0x2D | RAW14 |

接收端看到 DT = 0x2B，就知道后面的 payload 要按 RAW10 解；**协议元信息回答"如何解释 payload"**，不靠猜。

### Frame Start / Line Start / Line End / Frame End —— 回答"边界在哪"

```text
FS ── LS ── payload(第1行) ── LE
      LS ── payload(第2行) ── LE
      ...
      LS ── payload(第N行) ── LE ── FE
```

- **FS**（Frame Start 短包）：一帧开始，带 16 bit 帧号
- **LS / LE**：每行数据的起止
- **FE**（Frame End）：一帧结束

接收端就是靠这些同步包把连续比特流"切"回一帧帧图像。

### Virtual Channel（VC，2 bit）—— 回答"这是第几个 Camera"

DI 里还有 2 bit VC，把一条物理链路上的数据流分成 VC0~VC3 共 4 条**逻辑通道**：

```text
VC0 → Camera 0 / 图像数据
VC1 → Camera 1 / 内嵌元数据(曝光、增益等)
```

多摄像头 / 多数据流复用一条链路时靠 VC 区分。（今天只建立概念，多摄同步后续再深入。）

## ⑤ V4L2 处于什么位置？

```text
MIPI CSI-2 → CSI Receiver(硬件) → 驱动(内核) → V4L2(内核框架) → 用户空间
```

- **V4L2（Video4Linux2）= Linux 的标准摄像头框架/API**，不是硬件协议
- 用户空间看到的是 `/dev/videoN` 设备节点，用 `v4l2-ctl` / ioctl 访问：

```bash
v4l2-ctl --list-formats-ext
# 可能输出类似：
#   [0]: 'RG10' (10-bit Bayer RGRG/GBGB)        ← V4L2_PIX_FMT_SRGGB10
#   [1]: 'pRAA' (10-bit Bayer RGRG/GBGB packed) ← V4L2_PIX_FMT_SRGGB10P
```

看到 `SRGGB10` 要立刻拆解（Day 2 已学过）：

```text
S + RGGB + 10 = Sensor 的 Bayer 排列 RGGB + 10-bit RAW
```

两个容易混淆的格式概念：

| 概念 | 位置 | 例子 | 含义 |
| --- | --- | --- | --- |
| Media Bus Format | Sensor → CSI Receiver 的**总线上** | `MEDIA_BUS_FMT_SRGGB10_1X10` | 总线上的传输格式，`1X10` = 每像素 1 个 10-bit word（即 packed 传输） |
| Pixel Format | SoC **内存中**给用户空间看的格式 | `V4L2_PIX_FMT_SRGGB10` ('RG10') | 内存格式，2 B/px 未打包；`SRGGB10P` ('pRAA') 才是 1.25 B/px packed |

**呼应 Day 2 实验**：内存里 unpacked 2 B/px vs packed 1.25 B/px，就是 `raw10_packing.py` 里做的同一件事——packing 发生在 CSI-2 总线传输与内存存储这两个环节。

> NVIDIA Jetson 上：CSI Camera 走 `libargus + nvarguscamerasrc`（用 Jetson ISP）或 `v4l2src`（V4L2 路径）。
> 现在只认识名字，第 20~21 周深入 LibArgus。

---

## 实验 1：Camera 带宽计算器（calculate_bandwidth.py）

**为什么要做**：Day 2 的 README 里写过"约 2.47 MB/帧"——其实那个数字是 2.472 **MiB**（二进制），
被当成了 MB 写。带宽估算里 MB（10⁶）与 MiB（2²⁰）混用是最常见的错误，这个计算器把两种单位都显式给出。

```bash
python calculate_bandwidth.py
# 1920x1080  RAW10  30 fps  2 lane(s)
#   像素/帧      : 2,073,600
#   有效 byte/帧 : 2,592,000
#      = 2.592 MB/帧  (十进制)   ← 换算带宽时统一用这个
#      = 2.472 MiB/帧 (二进制)   ← Day 2 写的"2.47 MB"其实是这个
#   数据率       : 77.76 MB/s
#   有效载荷     : 0.622 Gbps
#   含开销(25%)链路: 0.778 Gbps
#   每 lane 承担 : 0.311 Gbps (载荷) / 0.389 Gbps (含开销)
#   最少 lane 数（按各代 D-PHY 速率）:
#     D-PHY v1.1   1.5 Gbps/lane -> 至少 1 lane
#     D-PHY v1.2   2.5 Gbps/lane -> 至少 1 lane
```

口径说明：字节数按 **packed 有效载荷**（RAW10 = 1.25 B/px）算；链路速率额外估算 **25% 协议开销**（FS/FE/LS/LE 同步包、包头 ECC、payload CRC、消隐期，实际链路利用率一般 75~85%）。

## 实验 2：参数扫描 —— 为什么 4K 需要更多 Lane？

`python calculate_bandwidth.py --table` 输出：

| 分辨率 | RAW | FPS | 像素/帧 | 载荷 MB/帧 | 数据率 MB/s | 数据率 Gbps | 含开销 Gbps | 最少 lane @1.5G | 最少 lane @2.5G |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1080P | RAW10 | 30 | 2,073,600 | 2.592 | 77.8 | 0.622 | 0.778 | 1 | 1 |
| 1080P | RAW10 | 60 | 2,073,600 | 2.592 | 155.5 | 1.244 | 1.555 | **2** | 1 |
| 4K | RAW10 | 30 | 8,294,400 | 10.368 | 311.0 | 2.488 | 3.110 | **3** | 2 |
| 4K | RAW12 | 30 | 8,294,400 | 12.442 | 373.2 | 2.986 | 3.732 | **3** | 2 |

从这张表读出的工程结论：

1. **帧率翻倍 = 数据率翻倍**：1080P30 用 1 个 1.5 Gbps lane 就够（0.778 Gbps），但 1080P60 立刻需要 2 lane——这就是很多 1080P 模块（如 IMX219）配 2 lane 的原因：给 60fps / 更高帧率留余量
2. **分辨率 4 倍 = 数据率 4 倍**：4K 像素数是 1080P 的 4 倍，数据率从 0.62 涨到 2.49 Gbps——所以 **4K Camera 通常需要更多 MIPI lane**，不是协议要求，是带宽算术
3. **留余量**：4K30 RAW10 在 2 lane × 2.5 Gbps 下勉强能跑（3.11 < 5.0）但只剩 ~40% 余量，跑不了 60fps；所以 4K 模块（如 IMX477）实际用 **4 lane**，单 lane 速率降到 ~0.75 Gbps，信号完整性更好、排线可以更长
4. **位深也花钱**：RAW12 比 RAW10 数据率高 20%（1.5 vs 1.25 B/px）

---

## 面试验收（今天学完应能回答）

**Q1：为什么 Camera Sensor 不直接输出 RGB？**
> Sensor 像素阵列通过 CFA 只采集单个颜色分量，因此输出 Bayer RAW；后续由 ISP 的 Demosaic 重建 RGB。直接输出 RGB 需要在 Sensor 内做完整 ISP，成本和功耗高、灵活性差。

**Q2：RAW10 是什么？**
> 每个 Bayer 像素用 10 bit 表示，范围 0~1023；MIPI CSI-2 上以 packed 方式传输（1.25 B/px）。

**Q3：为什么 4 个 RAW10 像素可以变成 5 个 byte？**
> 4 × 10 bit = 40 bit = 5 byte（Day 2 已用代码验证 round-trip）。

**Q4：MIPI Lane 是什么？**
> 一对差分线构成的高速串行数据通道；lane 越多总带宽越高，D-PHY 单 lane 速率 1.5~4.5 Gbps。

**Q5：MIPI CSI-2 和 V4L2 是一回事吗？**
> 不是。CSI-2 是 Camera 数据的**硬件传输协议**（物理层+包协议）；V4L2 是 Linux **内核/用户空间的视频设备框架与 API**（/dev/videoN、ioctl）。

**Q6：MEDIA_BUS_FMT_SRGGB10_1X10 是什么意思？**
> S = Sensor（对比 M = Memory）；RGGB = Bayer 排列；10 = 10 bit；1X10 = media bus 上每像素 1 个 10-bit word（packed 传输格式）。

## 结论

- MIPI CSI-2 用"时钟 lane + 1~4 数据 lane"的差分串行替代了 20+ 线的并行接口
- 数据按**包**组织：DI（VC + DT）回答"是什么、谁的"，FS/FE/LS/LE 回答"边界在哪"，ECC/CRC 保证可靠性
- RAW10 在 CSI-2 上的字节形态就是 Day 2 实验的 packed 格式（4 px → 5 B）
- 带宽 = 分辨率 × 帧率 × packed字节数，加上 ~25% 协议开销；lane 数是"数据率 ÷ 单 lane 速率"向上取整再加余量
- V4L2 是接收端之后、ISP 之前的 Linux 软件层，暴露 /dev/videoN 给应用
- 下一步（Day 4）：ISP 基础 + RAW → RGB 完整链路，之后才进入 BLC / DPC 等模块

## 运行方式

```bash
python calculate_bandwidth.py                                  # 默认 1080P RAW10 30fps 2 lanes
python calculate_bandwidth.py --width 3840 --height 2160 --bit-depth 12 --fps 30 --lanes 4
python calculate_bandwidth.py --table                          # 实验 2 对比表
```
