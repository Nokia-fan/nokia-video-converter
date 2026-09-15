# 编码模块

## 职责

`NokiaConverter._video_args()` 将设备、缩放方式、帧率和质量设置转换成 FFmpeg 视频参数；`_worker()` 负责组合音频与封装参数并执行。

## 接口

- 输入：`DEVICES` 设备预设及界面中的分辨率、编码器、帧率、码率、质量和缩放设置。
- 输出：传给 FFmpeg 的参数列表。
- 依赖：FFmpeg/ffprobe；`find_tool()` 在程序目录、子目录或 PATH 中定位工具。

## 兼容策略

- E72/E71：MPEG-4 Simple Profile，禁用 B 帧、QPel、GMC。
- N95/N82：H.264 Constrained Baseline，禁用 CABAC、B 帧和 weighted P，使用单参考帧。
- MP4：`mp42` 主品牌与 faststart；3GP 不设置 MP4 品牌。
- 所有路线：YUV420P、方形像素、恒定输出帧率。

调用方只应通过设备预设和界面字段配置编码，不应在队列或窗口代码中拼接额外编码参数。

## 界面路径显示

`_sync_outdir_display()` 只把主目录内的输出地址缩写为 `~/…` 供顶部状态栏显示；`self.outdir` 始终保留实际路径。

## 发布边界

公开仓库只包含通用转换器、启动脚本和模块文档。带有本机路径、私人媒体名称或特定部署逻辑的一次性脚本由 `.gitignore` 排除。
