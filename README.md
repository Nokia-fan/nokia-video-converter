# 诺基亚视频转换器

把常见视频转换成适合诺基亚老手机原生播放器的格式。界面简单、支持批量任务，也允许熟悉编码的用户详细调整。


## 它能解决什么

- 为具体手机选择经过限制的编码参数，减少旧播放器中的噪点、花屏和无法解析。
- 五档质量与体积，从“极省空间”到“最高质量”，不用自己计算码率。
- 批量选择视频或添加整个文件夹，并显示总进度、当前阶段、速度和剩余时间。
- 保持原比例且默认不加黑边；也可按宽度、按高度、裁剪铺满或强制拉伸。
- 正确处理横屏、竖屏、旋转元数据和非方形像素。
- 支持二遍编码、去隔行、音量标准化及自定义分辨率、帧率和码率。
- 兼容 Windows 和 Linux；程序本身仅使用 Python 标准库，编码由 FFmpeg 完成。

## 支持的预设

| 设备 | 默认视频路线 | 用途 |
| --- | --- | --- |
| Nokia E72 | MPEG-4 Simple Profile，320×240，20 fps | 优先兼容自带 RealPlayer |
| Nokia E71 / E63 | MPEG-4 Simple Profile，15 fps | 降低较弱机型的解码压力 |
| Nokia N95 / N82 | H.264 Constrained Baseline，25 fps | 参考诺基亚原厂 Nseries 视频路线 |
| Nokia 5800 / 5230 / X6 | H.264 Baseline，640×360 | S60 触屏机型 |
| Nokia N8 / E7 / C7 | H.264 Baseline，640×360 | Symbian^3 机型 |
| Nokia S40 通用 | H.263 + AAC，320×240，15 fps | 兼容优先 |

这些是稳妥的起点，并不代表每台手机、每张存储卡和每个播放器版本都完全相同。遇到偶发彩块时，建议先用“均衡”转换同一小段进行测试。

## 下载与启动

### Windows

1. 在仓库页面右侧 **Releases** 下载最新版 ZIP；如果暂时没有 Release，也可点绿色 **Code → Download ZIP**。
2. 安装 [Python 3](https://www.python.org/downloads/windows/)；安装时勾选 **Add Python to PATH**。
3. 安装 [FFmpeg](https://ffmpeg.org/download.html)，或者把 `ffmpeg.exe` 和 `ffprobe.exe` 放进本工具文件夹、`bin` 或 `ffmpeg\bin`。
4. 双击 `run-windows.bat`。

### Linux

安装 Python 3、Tk 和 FFmpeg，然后运行：

```bash
./run.sh
```

Fedora：

```bash
sudo dnf install python3 python3-tkinter ffmpeg
```

Ubuntu / Debian：

```bash
sudo apt install python3 python3-tk ffmpeg
```

## 三步转换

1. 选择手机型号和质量档位。
2. 点击“批量选择视频”或“添加文件夹”，确认顶部输出目录。
3. 点击绿色“开始转换”；完成后可直接打开输出文件夹。

默认“智能适配屏幕”会保持画面比例且不补黑边：横屏限制宽度，竖屏限制高度。例如 E72 的 16:9 横屏视频通常输出为 320×180，9:16 竖屏视频通常输出为约 134×240。

## 质量档位

| 档位 | 特点 | 建议场景 |
| --- | --- | --- |
| 极省空间 | 最小体积，细节损失较明显 | 临时观看、存储极紧张 |
| 省空间 | 小体积与可看画质 | 动画、讲话、批量剧集 |
| 均衡（推荐） | 画质、体积、解码压力折中 | 大多数视频 |
| 高质量 | 保留更多运动和纹理细节 | 舞蹈、演出、复杂画面 |
| 最高质量 | 最大码率，文件也最大 | 短片或画质对比 |

文件体积主要由总码率决定：`(视频码率 + 音频码率) × 时长`。二遍编码会更慢，但能更稳定地分配码率和控制体积。

## 命令行

没有图形环境时，可以直接使用 E72 兼容路线转换：

```bash
python3 nokia_video_converter.py "输入视频.mp4" -o "输出目录" -q balanced
```

`-q` 可选：`tiny`、`small`、`balanced`、`high`、`best`。

## 项目边界与隐私

仓库只包含通用转换器、启动脚本和技术说明。个人视频、转换结果、FFmpeg 二遍日志及含本机路径的一次性批处理脚本不会上传。

这是爱好者制作的非官方工具，与 Nokia/HMD Global 无隶属或认可关系。Nokia 是其各自权利人的商标。

## 许可

本项目采用 [MIT License](LICENSE)。欢迎使用、修改和分享；如果你遇到某个型号不能播放或画面异常，也欢迎提交 Issue，并附上手机型号、播放器、源视频信息和所用档位。
