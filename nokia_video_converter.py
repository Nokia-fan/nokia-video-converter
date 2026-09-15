#!/usr/bin/env python3
"""Nokia 老手机视频转换器（仅依赖 Python 标准库和 FFmpeg）。"""

from __future__ import annotations

import json
import os
import platform
import queue
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:  # 命令行模式不依赖 Tk
    tk = None


@dataclass(frozen=True)
class Device:
    size: str
    codec: str
    fps: int
    vbitrate: int
    abitrate: int
    audio_rate: int
    note: str


DEVICES = {
    "诺基亚 E72（推荐/原生播放器）": Device("320x240", "mpeg4", 20, 500, 64, 44100, "稳定优化：20fps、短关键帧、受控峰值；兼顾缩放清晰度与 E72 解码能力"),
    "诺基亚 E71 / E63": Device("320x240", "mpeg4", 15, 400, 64, 44100, "较弱机型使用 15fps，降低瞬时解码压力"),
    "诺基亚 N95 / N82（原厂 H.264 路线）": Device("320x240", "libx264", 25, 640, 96, 44100, "参考原厂 Nseries：H.264 Constrained Baseline、25fps、无 B 帧"),
    "诺基亚 5800 / 5230 / X6": Device("640x360", "libx264", 25, 800, 96, 44100, "H.264 Baseline，适合 640×360 触屏 S60"),
    "诺基亚 N8 / E7 / C7": Device("640x360", "libx264", 25, 1100, 96, 44100, "H.264 Baseline，Symbian^3 机型"),
    "诺基亚 S40 通用（最兼容）": Device("320x240", "h263", 15, 220, 48, 22050, "3GP/H.263 + AAC，画质较低但兼容范围最大"),
}

QUALITIES = {
    "极省空间": (0.55, 0.75),
    "省空间": (0.75, 0.85),
    "均衡（推荐）": (1.0, 1.0),
    "高质量": (1.35, 1.15),
    "最高质量": (1.75, 1.3),
}

SCALE_MODES = (
    "智能适配屏幕（推荐，无黑边）",
    "按长边缩放（无黑边）",
    "按宽度缩放（无黑边）",
    "按高度缩放（无黑边）",
    "适应屏幕（保持比例并补黑边）",
    "裁剪铺满（保持比例，无黑边）",
    "强制拉伸到目标分辨率",
    "保留原分辨率",
)

PORTRAIT_MODES = (
    "保持拍摄方向（推荐）",
    "竖屏自动顺时针旋转为横屏",
)

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg", ".ts", ".mts", ".3gp"}


def app_dir() -> Path:
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


def find_tool(name: str) -> str | None:
    """支持 PATH，以及放在程序旁或 ffmpeg/bin 中的 Windows 版本。"""
    exe = name + (".exe" if os.name == "nt" else "")
    for candidate in (app_dir() / exe, app_dir() / "ffmpeg" / "bin" / exe, app_dir() / "bin" / exe):
        if candidate.is_file():
            return str(candidate)
    return shutil.which(exe) or shutil.which(name)


class NokiaConverter(tk.Tk if tk else object):
    def __init__(self) -> None:
        super().__init__()
        self.title("诺基亚视频转换器 v1.7")
        self.geometry("980x720")
        self.minsize(780, 560)
        self.files: list[Path] = []
        self.running = False
        self.cancelled = False
        self.proc: subprocess.Popen | None = None
        self.ffmpeg = find_tool("ffmpeg")
        self.ffprobe = find_tool("ffprobe")
        self.started_at = 0.0
        self.events: queue.Queue = queue.Queue()
        self._make_vars()
        self._build()
        self.after(100, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _make_vars(self) -> None:
        self.device = tk.StringVar(value=next(iter(DEVICES)))
        self.quality = tk.StringVar(value="均衡（推荐）")
        self.outdir = tk.StringVar(value=str(Path.home() / "Videos" / "Nokia"))
        self.outdir_display = tk.StringVar()
        self.outdir.trace_add("write", self._sync_outdir_display)
        self._sync_outdir_display()
        self.size = tk.StringVar()
        self.codec = tk.StringVar()
        self.fps = tk.StringVar()
        self.vbitrate = tk.StringVar()
        self.abitrate = tk.StringVar()
        self.audio_rate = tk.StringVar()
        self.scale_mode = tk.StringVar(value=SCALE_MODES[0])
        self.portrait_mode = tk.StringVar(value=PORTRAIT_MODES[0])
        self.stereo = tk.BooleanVar(value=True)
        self.two_pass = tk.BooleanVar(value=True)
        self.deinterlace = tk.BooleanVar(value=False)
        self.normalize = tk.BooleanVar(value=False)
        self.overwrite = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="添加视频后即可开始")
        self.progress_text = tk.StringVar(value="尚未开始")
        self.progress = tk.DoubleVar(value=0)

    def _build(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        title = ttk.Label(root, text="诺基亚视频转换器  v1.7", font=("sans", 19, "bold"))
        title.pack(anchor="w")
        ttk.Label(root, text="为老款诺基亚原生播放器生成稳定、清晰且体积可控的视频").pack(anchor="w", pady=(2, 12))

        top = ttk.Frame(root)
        top.pack(fill="x")
        ttk.Label(top, text="手机型号").grid(row=0, column=0, sticky="w")
        box = ttk.Combobox(top, textvariable=self.device, values=list(DEVICES), state="readonly", width=35)
        box.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        box.bind("<<ComboboxSelected>>", lambda _e: self._apply_preset())
        ttk.Label(top, text="质量/体积").grid(row=0, column=1, sticky="w")
        qbox = ttk.Combobox(top, textvariable=self.quality, values=list(QUALITIES), state="readonly", width=18)
        qbox.grid(row=1, column=1, sticky="ew", padx=(0, 10))
        qbox.bind("<<ComboboxSelected>>", lambda _e: self._apply_preset())
        ttk.Button(top, text="批量选择视频…", command=self._add).grid(row=1, column=2, padx=3)
        ttk.Button(top, text="添加文件夹…", command=self._add_folder).grid(row=1, column=3, padx=3)
        ttk.Button(top, text="移除", command=self._remove).grid(row=1, column=4, padx=3)
        ttk.Button(top, text="清空", command=self._clear).grid(row=1, column=5, padx=3)
        top.columnconfigure(0, weight=2); top.columnconfigure(1, weight=1)

        # 固定在顶部，不能被会扩展的文件列表或高级选项挤出窗口。
        scaling = ttk.LabelFrame(root, text="画面设置（保持可见）", padding=(10, 7))
        scaling.pack(fill="x", pady=(9, 0))
        ttk.Label(scaling, text="缩放方式：").grid(row=0, column=0, sticky="w")
        ttk.Combobox(scaling, textvariable=self.scale_mode, values=SCALE_MODES,
                     state="readonly", width=34).grid(row=0, column=1, sticky="ew", padx=(3, 16))
        ttk.Label(scaling, text="竖屏处理：").grid(row=0, column=2, sticky="w")
        ttk.Combobox(scaling, textvariable=self.portrait_mode, values=PORTRAIT_MODES,
                     state="readonly", width=29).grid(row=0, column=3, sticky="ew", padx=(3, 0))
        scaling.columnconfigure(1, weight=1); scaling.columnconfigure(3, weight=1)
        ttk.Label(scaling, text="默认智能模式：横屏限制宽度、竖屏限制高度，保持比例且不加黑边",
                  foreground="#555555").grid(row=1, column=0, columnspan=4, sticky="w", pady=(5, 0))

        # 关键操作置于顶部，窗口较矮时也不会被遮住。
        action = ttk.Frame(root, padding=(0, 10, 0, 2))
        action.pack(fill="x")
        self.start_btn = tk.Button(action, text="▶  开始转换", command=self._start,
                                   bg="#16833b", fg="white", activebackground="#116c31",
                                   activeforeground="white", font=("sans", 12, "bold"),
                                   padx=24, pady=7, relief="flat", cursor="hand2")
        self.start_btn.pack(side="left")
        self.cancel_btn = ttk.Button(action, text="取消转换", command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=8)
        ttk.Label(action, text="输出到：").pack(side="left", padx=(14, 3))
        ttk.Label(action, textvariable=self.outdir_display, foreground="#1769aa").pack(side="left", fill="x", expand=True)
        ttk.Button(action, text="打开输出文件夹", command=self._open_out).pack(side="right")

        # 进度区固定在开始按钮下方，不受文件列表和高级选项高度影响。
        progress_box = ttk.LabelFrame(root, text="转换进度", padding=(10, 7))
        progress_box.pack(fill="x", pady=(7, 2))
        self.bar = ttk.Progressbar(progress_box, variable=self.progress, maximum=100, mode="determinate")
        self.bar.pack(fill="x", ipady=5)
        ttk.Label(progress_box, textvariable=self.progress_text, anchor="center",
                  font=("sans", 10, "bold")).pack(fill="x", pady=(5, 0))
        ttk.Label(progress_box, textvariable=self.status, anchor="center",
                  foreground="#555555").pack(fill="x", pady=(2, 0))

        frame = ttk.Frame(root)
        frame.pack(fill="both", expand=True, pady=10)
        self.listbox = tk.Listbox(frame, selectmode="extended", height=10)
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")

        self.note = ttk.Label(root, foreground="#1769aa")
        self.note.pack(anchor="w", pady=(0, 6))
        adv = ttk.LabelFrame(root, text="详细调节（改动后以这里的参数为准）", padding=10)
        adv.pack(fill="x")
        fields = [("分辨率", self.size, 12), ("视频编码", self.codec, 12), ("帧率", self.fps, 7),
                  ("视频码率 kbps", self.vbitrate, 9), ("音频码率 kbps", self.abitrate, 9), ("采样率 Hz", self.audio_rate, 9)]
        for i, (label, var, width) in enumerate(fields):
            ttk.Label(adv, text=label).grid(row=0, column=i, sticky="w", padx=3)
            ttk.Entry(adv, textvariable=var, width=width).grid(row=1, column=i, sticky="ew", padx=3)
            adv.columnconfigure(i, weight=1)
        checks = ttk.Frame(adv)
        checks.grid(row=2, column=0, columnspan=6, sticky="w", pady=(9, 0))
        ttk.Checkbutton(checks, text="立体声", variable=self.stereo).pack(side="left", padx=(0, 13))
        ttk.Checkbutton(checks, text="二遍编码（体积更准）", variable=self.two_pass).pack(side="left", padx=(0, 13))
        ttk.Checkbutton(checks, text="去隔行", variable=self.deinterlace).pack(side="left", padx=(0, 13))
        ttk.Checkbutton(checks, text="音量标准化", variable=self.normalize).pack(side="left", padx=(0, 13))
        ttk.Checkbutton(checks, text="覆盖同名文件", variable=self.overwrite).pack(side="left")

        out = ttk.Frame(root)
        out.pack(fill="x", pady=(10, 5))
        ttk.Label(out, text="更改输出目录").pack(side="left")
        ttk.Entry(out, textvariable=self.outdir).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(out, text="选择…", command=self._choose_out).pack(side="left")
        self._apply_preset()

    def _sync_outdir_display(self, *_args) -> None:
        """Show a compact home-relative path without changing the actual output path."""
        value = self.outdir.get()
        try:
            path = Path(value).expanduser()
            home = Path.home()
            self.outdir_display.set(str(Path("~") / path.relative_to(home)))
        except (ValueError, TypeError):
            self.outdir_display.set(value)

    def _apply_preset(self) -> None:
        d = DEVICES[self.device.get()]
        vm, am = QUALITIES[self.quality.get()]
        self.size.set(d.size); self.codec.set(d.codec); self.fps.set(str(d.fps))
        self.vbitrate.set(str(round(d.vbitrate * vm))); self.abitrate.set(str(round(d.abitrate * am)))
        self.audio_rate.set(str(d.audio_rate)); self.note.configure(text=d.note)
        self._refresh()

    def _add(self) -> None:
        names = filedialog.askopenfilenames(title="选择视频", filetypes=[("视频文件", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.mpg *.mpeg *.ts *.mts *.3gp"), ("所有文件", "*")])
        for name in names:
            p = Path(name)
            if p not in self.files:
                self.files.append(p)
        self._refresh()

    def _add_folder(self) -> None:
        name = filedialog.askdirectory(title="选择包含视频的文件夹")
        if not name:
            return
        found = [p for p in Path(name).rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS]
        for p in sorted(found):
            if p not in self.files:
                self.files.append(p)
        self._refresh()
        if not found:
            messagebox.showinfo("没有找到视频", "所选文件夹中没有找到支持的视频文件。")

    def _remove(self) -> None:
        for i in reversed(self.listbox.curselection()):
            del self.files[i]
        self._refresh()

    def _clear(self) -> None:
        self.files.clear(); self._refresh()

    def _refresh(self) -> None:
        self.listbox.delete(0, "end")
        for p in self.files:
            self.listbox.insert("end", str(p))
        if self.files and not self.running:
            try:
                vb, ab = int(self.vbitrate.get()), int(self.abitrate.get())
                self.status.set(f"已添加 {len(self.files)} 个视频；预计每小时约 {(vb + ab) * 3600 / 8 / 1024:.0f} MB")
            except ValueError:
                self.status.set(f"已添加 {len(self.files)} 个视频")

    def _choose_out(self) -> None:
        d = filedialog.askdirectory(initialdir=self.outdir.get())
        if d: self.outdir.set(d)

    def _open_out(self) -> None:
        path = Path(self.outdir.get())
        path.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            messagebox.showerror("无法打开文件夹", f"输出目录是：\n{path}\n\n{e}")

    def _probe(self, path: Path) -> float:
        cmd = [self.ffprobe or "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)]
        data = json.loads(subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT))
        return float(data["format"]["duration"])

    def _validate(self) -> tuple[int, int, int, int]:
        if not self.files: raise ValueError("请先添加至少一个视频")
        self.ffmpeg, self.ffprobe = find_tool("ffmpeg"), find_tool("ffprobe")
        if not self.ffmpeg or not self.ffprobe:
            raise ValueError("找不到 FFmpeg/ffprobe。Windows 可把 ffmpeg.exe 和 ffprobe.exe 放到程序同一文件夹。")
        try:
            w, h = map(int, self.size.get().lower().split("x")); fps = int(self.fps.get())
            vb, ab, ar = int(self.vbitrate.get()), int(self.abitrate.get()), int(self.audio_rate.get())
        except Exception: raise ValueError("详细参数格式不正确，请检查分辨率和数字项")
        if min(w, h, fps, vb, ab, ar) <= 0 or w % 2 or h % 2: raise ValueError("分辨率须为正偶数，所有数值须大于 0")
        if self.codec.get() not in {"mpeg4", "libx264", "h263"}: raise ValueError("视频编码仅支持 mpeg4、libx264 或 h263")
        return vb, ab, ar, fps

    def _start(self) -> None:
        try: self._validate()
        except ValueError as e: messagebox.showerror("无法开始", str(e)); return
        Path(self.outdir.get()).mkdir(parents=True, exist_ok=True)
        self.running = True; self.cancelled = False; self.progress.set(0); self.started_at = time.monotonic()
        self.progress_text.set(f"准备转换，共 {len(self.files)} 个文件…")
        self.start_btn.configure(state="disabled"); self.cancel_btn.configure(state="normal")
        threading.Thread(target=self._worker, daemon=True).start()

    def _output_path(self, src: Path) -> Path:
        ext = ".3gp" if self.codec.get() == "h263" else ".mp4"
        return Path(self.outdir.get()) / f"{src.stem}_NOKIA{ext}"

    def _video_args(self, pass_no: int | None = None, passlog: str = "") -> list[str]:
        w, h = self.size.get().lower().split("x")
        mode = self.scale_mode.get()
        # FFmpeg 默认先应用手机/相机的旋转元数据。这里再允许用户把真正的竖屏画面转为横屏。
        prefix = ""
        if self.portrait_mode.get() == PORTRAIT_MODES[1]:
            prefix = "transpose=clock:passthrough=landscape,"
        # 先将非方形像素转换成实际显示比例，防止 DVD/老 AVI 等来源被压扁或拉宽。
        prefix += "scale=trunc(iw*sar/2)*2:trunc(ih/2)*2,setsar=1,"
        if mode == SCALE_MODES[0]:
            vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1"
        elif mode == SCALE_MODES[1]:
            edge = max(int(w), int(h))
            vf = f"scale='if(gte(iw,ih),{edge},-2)':'if(gte(iw,ih),-2,{edge})',setsar=1"
        elif mode == SCALE_MODES[2]:
            vf = f"scale={w}:-2,setsar=1"
        elif mode == SCALE_MODES[3]:
            vf = f"scale=-2:{h},setsar=1"
        elif mode == SCALE_MODES[4]:
            vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1"
        elif mode == SCALE_MODES[5]:
            vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
        elif mode == SCALE_MODES[6]:
            vf = f"scale={w}:{h},setsar=1"
        else:
            # 老式编码器要求偶数尺寸；只在必要时向下取整 1 像素。
            vf = "scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1"
        vf = prefix + vf
        if self.deinterlace.get(): vf = "yadif," + vf
        codec = self.codec.get(); args = ["-vf", vf, "-r", self.fps.get(), "-pix_fmt", "yuv420p", "-c:v", codec]
        if codec == "mpeg4": args += ["-profile:v", "0", "-level", "3", "-bf", "0"]
        elif codec == "libx264":
            # 320×240 及按高度生成的约 426×240 使用 Level 2.1；宽屏机型使用 Level 3.0。
            level = "2.1" if int(h) <= 240 else "3.0"
            args += ["-profile:v", "baseline", "-level", level,
                     "-x264-params", "bframes=0:ref=1:cabac=0:weightp=0",
                     "-g", str(int(self.fps.get()) * 2)]
        else: args += ["-g", str(int(self.fps.get()) * 2)]
        vb = self.vbitrate.get()
        peak = round(int(vb) * 1.25)
        # 一秒 GOP 限制花屏传播；适度峰值避免舞蹈/粒子等复杂画面突然糊成块。
        if codec == "mpeg4":
            qmax = {"极省空间": 24, "省空间": 20, "均衡（推荐）": 16, "高质量": 13, "最高质量": 11}[self.quality.get()]
            args += ["-g", self.fps.get(), "-mbd", "rd", "-trellis", "1", "-qmin", "2", "-qmax", str(qmax), "-qcomp", "0.65"]
        args += ["-b:v", f"{vb}k", "-maxrate", f"{peak}k", "-bufsize", f"{peak * 2}k", "-fps_mode", "cfr"]
        if pass_no: args += ["-pass", str(pass_no), "-passlogfile", passlog]
        return args

    def _run(self, cmd: list[str], duration: float, base: float, span: float,
             file_no: int, total: int, stage: str) -> None:
        popen_extra = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, errors="replace", **popen_extra)
        assert self.proc.stdout
        speed = ""
        for line in self.proc.stdout:
            if self.cancelled: break
            line = line.strip()
            if line.startswith("speed="):
                speed = line.split("=", 1)[1]
            if line.startswith("out_time_ms="):
                try:
                    current = min(1, int(line.split("=", 1)[1]) / 1_000_000 / duration)
                    self.events.put(("progress", (base + current * span, file_no, total, stage, current * 100, speed)))
                except (ValueError, ZeroDivisionError): pass
        if self.cancelled and self.proc.poll() is None: self.proc.terminate()
        code = self.proc.wait()
        if code and not self.cancelled: raise RuntimeError(f"FFmpeg 转换失败（退出码 {code}）")

    def _worker(self) -> None:
        try:
            total = len(self.files)
            for idx, src in enumerate(self.files):
                if self.cancelled: break
                self.events.put(("status", f"正在处理 {idx + 1}/{total}：{src.name}"))
                duration = self._probe(src); out = self._output_path(src)
                if out.exists() and not self.overwrite.get():
                    n = 2
                    while out.with_name(f"{out.stem}_{n}{out.suffix}").exists(): n += 1
                    out = out.with_name(f"{out.stem}_{n}{out.suffix}")
                common = [self.ffmpeg or "ffmpeg", "-hide_banner", "-y", "-i", str(src), "-map", "0:v:0", "-map", "0:a:0?", "-map_metadata", "-1"]
                base, unit = idx * 100 / total, 100 / total
                use_two = self.two_pass.get()
                passlog = str(Path(self.outdir.get()) / f".nokia-pass-{os.getpid()}-{idx}")
                if use_two:
                    cmd1 = common + self._video_args(1, passlog) + ["-an", "-f", "null", os.devnull, "-progress", "pipe:1", "-nostats"]
                    self._run(cmd1, duration, base, unit * .45, idx + 1, total, "第一遍：分析画面")
                if self.cancelled: break
                audio = ["-c:a", "aac", "-profile:a", "aac_low", "-b:a", f"{self.abitrate.get()}k", "-ar", self.audio_rate.get(), "-ac", "2" if self.stereo.get() else "1"]
                if self.normalize.get(): audio += ["-af", "loudnorm=I=-16:TP=-2:LRA=11"]
                mux = ["-movflags", "+faststart"]
                if out.suffix.lower() == ".mp4":
                    mux += ["-brand", "mp42"]
                mux += ["-metadata", "comment=Converted for Nokia", "-progress", "pipe:1", "-nostats", str(out)]
                cmd2 = common + self._video_args(2 if use_two else None, passlog) + audio + mux
                self._run(cmd2, duration, base + (unit * .45 if use_two else 0), unit * (.55 if use_two else 1),
                          idx + 1, total, "第二遍：生成视频" if use_two else "正在生成视频")
                for suffix in ("-0.log", "-0.log.mbtree"):
                    try: Path(passlog + suffix).unlink()
                    except FileNotFoundError: pass
            self.events.put(("done", self.cancelled))
        except Exception as e: self.events.put(("error", str(e)))

    def _poll(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "progress":
                    percent, file_no, total, stage, stage_percent, speed = value
                    self.progress.set(percent)
                    elapsed = max(0, time.monotonic() - self.started_at)
                    eta = elapsed * (100 - percent) / percent if percent > 0.1 else 0
                    speed_text = f" · 速度 {speed}" if speed and speed != "N/A" else ""
                    eta_text = self._clock(eta) if percent > 0.1 else "计算中"
                    self.progress_text.set(
                        f"总进度 {percent:.1f}% · 文件 {file_no}/{total} · {stage} {stage_percent:.0f}%"
                        f"{speed_text} · 已用 {self._clock(elapsed)} · 约剩 {eta_text}"
                    )
                elif kind == "status": self.status.set(value)
                elif kind == "done":
                    self.running = False; self.start_btn.configure(state="normal"); self.cancel_btn.configure(state="disabled")
                    self.status.set("已取消" if value else "转换完成")
                    self.progress_text.set("转换已取消" if value else f"总进度 100% · 全部 {len(self.files)} 个文件已完成")
                    if not value:
                        self.progress.set(100)
                        if messagebox.askyesno("转换完成", f"视频已保存到：\n{self.outdir.get()}\n\n现在打开输出文件夹吗？"):
                            self._open_out()
                elif kind == "error":
                    self.running = False; self.start_btn.configure(state="normal"); self.cancel_btn.configure(state="disabled")
                    self.status.set("转换失败"); messagebox.showerror("转换失败", value)
                    self.progress_text.set("转换失败，请查看提示")
        except queue.Empty: pass
        self.after(100, self._poll)

    @staticmethod
    def _clock(seconds: float) -> str:
        seconds = max(0, int(seconds))
        hours, rem = divmod(seconds, 3600)
        minutes, secs = divmod(rem, 60)
        return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"

    def _cancel(self) -> None:
        self.cancelled = True; self.status.set("正在取消…")
        if self.proc and self.proc.poll() is None: self.proc.terminate()

    def _close(self) -> None:
        if self.running and not messagebox.askyesno("退出", "转换仍在进行，确定退出吗？"): return
        self._cancel(); self.destroy()


def cli() -> int:
    """无图形环境时提供可用的 E72 均衡转换后备。"""
    import argparse
    parser = argparse.ArgumentParser(description="诺基亚 E72 视频转换器")
    parser.add_argument("inputs", nargs="+", help="输入视频")
    parser.add_argument("-o", "--output-dir", default="Nokia", help="输出目录")
    parser.add_argument("-q", "--quality", choices=["tiny", "small", "balanced", "high", "best"], default="balanced")
    args = parser.parse_args()
    ffmpeg = find_tool("ffmpeg")
    if not ffmpeg:
        print("找不到 FFmpeg。请安装 FFmpeg，或将 ffmpeg.exe 放在程序目录。", file=sys.stderr)
        return 2
    rates = {"tiny": (230, 48), "small": (320, 56), "balanced": (420, 64), "high": (570, 72), "best": (735, 83)}
    vb, ab = rates[args.quality]; outdir = Path(args.output_dir); outdir.mkdir(parents=True, exist_ok=True)
    for name in args.inputs:
        src = Path(name); out = outdir / f"{src.stem}_NOKIA.mp4"
        cmd = [ffmpeg, "-hide_banner", "-y", "-i", str(src), "-map", "0:v:0", "-map", "0:a:0?",
               "-vf", "scale=320:240:force_original_aspect_ratio=decrease,pad=320:240:(ow-iw)/2:(oh-ih)/2,setsar=1",
               "-r", "25", "-pix_fmt", "yuv420p", "-c:v", "mpeg4", "-profile:v", "0", "-level", "3",
               "-bf", "0", "-g", "50", "-b:v", f"{vb}k", "-maxrate", f"{vb}k", "-bufsize", f"{vb*2}k",
               "-c:a", "aac", "-profile:a", "aac_low", "-b:a", f"{ab}k", "-ar", "44100", "-ac", "2",
               "-movflags", "+faststart", str(out)]
        print(f"转换：{src} -> {out}")
        if subprocess.run(cmd).returncode: return 1
    return 0


if __name__ == "__main__":
    if tk is None:
        import sys
        if len(sys.argv) == 1:
            print("缺少 Tk 图形库。Fedora 请安装 python3-tkinter；也可使用命令行：\n"
                  "python3 nokia_video_converter.py 视频.mp4 -o 输出目录", file=sys.stderr)
            raise SystemExit(2)
        raise SystemExit(cli())
    NokiaConverter().mainloop()
