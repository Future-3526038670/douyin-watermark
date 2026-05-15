import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime

from core.parser import parse_douyin_link
from core.downloader import download_video, get_desktop_path

# ── 配色 ──
C = {
    "bg":       "#eef1f5",
    "header":   "#0f172a",
    "header_fg":"#f1f5f9",
    "card":     "#ffffff",
    "primary":  "#0284c7",
    "primary_h":"#0369a1",
    "green":    "#059669",
    "green_h":  "#047857",
    "gray":     "#64748b",
    "gray_h":   "#475569",
    "text":     "#111827",
    "text2":    "#6b7280",
    "input_bg": "#f8fafc",
    "input_bd": "#cbd5e1",
    "focus_bd": "#0284c7",
    "list_bg":  "#f8fafc",
    "list_sel": "#dbeafe",
    "bar_track":"#e2e8f0",
    "bar_fill": "#0284c7",
    "status_bg":"#e5e7eb",
    "status_fg":"#4b5563",
}

FT = ("微软雅黑", 16, "bold")
FH = ("微软雅黑", 11, "bold")
FN = ("微软雅黑", 10)
FS = ("微软雅黑", 9)
FM = ("Consolas", 11)


def _rr(canvas, x1, y1, x2, y2, r=10, **kw):
    pts = [
        x1+r, y1, x2-r, y1, x2, y1, x2, y1+r,
        x2, y2-r, x2, y2, x2-r, y2, x1+r, y2,
        x1, y2, x1, y2-r, x1, y1+r, x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


# ────────────────────────────────────────
# 圆角按钮（Canvas 包在 Frame 里）
# ────────────────────────────────────────
class RoundBtn:
    def __init__(self, parent, text, color, color_h, cmd=None, w=100, h=36, font=FN):
        self._frame = tk.Frame(parent)
        self._cv = tk.Canvas(self._frame, width=w, height=h,
                             highlightthickness=0, bd=0, cursor="hand2")
        self._cv.pack()
        self._text, self._color, self._color_h = text, color, color_h
        self._cmd, self._font = cmd, font
        self._w, self._h = w, h
        self._enabled = True
        self._draw(color)
        self._cv.bind("<Button-1>", lambda e: self._cmd() if self._enabled and self._cmd else None)
        self._cv.bind("<Enter>", lambda e: self._draw(self._color_h) if self._enabled else None)
        self._cv.bind("<Leave>", lambda e: self._draw(self._color) if self._enabled else None)

    def pack(self, **kw):
        self._frame.pack(**kw)

    def grid(self, **kw):
        self._frame.grid(**kw)

    def _draw(self, color):
        c = self._cv
        c.delete("all")
        _rr(c, 0, 0, self._w, self._h, r=8, fill=color, outline=color)
        c.create_text(self._w // 2, self._h // 2, text=self._text,
                      fill="white", font=self._font)

    def set_enabled(self, val):
        self._enabled = val
        self._draw(self._color if val else "#94a3b8")
        self._cv.config(cursor="hand2" if val else "arrow")


# ────────────────────────────────────────
# 圆角进度条
# ────────────────────────────────────────
class RoundBar(tk.Canvas):
    def __init__(self, master, h=10, **kw):
        super().__init__(master, height=h, highlightthickness=0, bd=0, **kw)
        self._h = h
        self._val = 0
        self._max = 100
        self.bind("<Configure>", lambda e: self._draw())

    def set_value(self, v):
        self._val = min(max(v, 0), self._max)
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self._h
        if w < 2:
            return
        r = h // 2
        _rr(self, 0, 0, w, h, r=r, fill=C["bar_track"], outline=C["bar_track"])
        fw = (self._val / self._max) * w if self._max else 0
        if fw > 2:
            _rr(self, 0, 0, max(fw, h), h, r=r, fill=C["bar_fill"], outline=C["bar_fill"])


# ────────────────────────────────────────
# 卡片
# ────────────────────────────────────────
def card(parent, title):
    outer = tk.Frame(parent, bg=C["bg"])
    bar = tk.Frame(outer, bg=C["primary"], width=4)
    bar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 0))
    inner = tk.Frame(outer, bg=C["card"], padx=16, pady=12)
    inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    tk.Label(inner, text=title, font=FH, bg=C["card"], fg=C["text"]).pack(anchor=tk.W, pady=(0, 8))
    return outer, inner


# ────────────────────────────────────────
# 主界面
# ────────────────────────────────────────
class DouyinApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("抖音去水印")
        self.root.geometry("700x620")
        self.root.minsize(620, 580)
        self.root.configure(bg=C["bg"])
        self.current_video_info = None
        self.download_dir = get_desktop_path()
        self._build()
        self._center()

    def _center(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _input(self, parent, font=FN, readonly=False, textvariable=None):
        """创建圆角风格输入框（Frame 边框 + Entry 内容）。"""
        frame = tk.Frame(parent, bg=C["input_bd"], padx=1, pady=1)
        entry = tk.Entry(
            frame, font=font, bg=C["input_bg"], fg=C["text"],
            insertbackground=C["text"], relief=tk.FLAT, bd=0,
            highlightthickness=0, textvariable=textvariable,
        )
        if readonly:
            entry.config(state="readonly", readonlybackground=C["list_bg"])
        entry.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        entry.bind("<FocusIn>", lambda e: frame.config(bg=C["focus_bd"]))
        entry.bind("<FocusOut>", lambda e: frame.config(bg=C["input_bd"]))
        return frame, entry

    def _build(self):
        # ── 标题栏 ──
        header = tk.Frame(self.root, bg=C["header"], height=56)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="抖音去水印", font=FT, bg=C["header"],
                 fg=C["header_fg"]).pack(side=tk.LEFT, padx=24)
        tk.Label(header, text="粘贴分享链接，一键下载无水印视频", font=FS,
                 bg=C["header"], fg="#94a3b8").pack(side=tk.LEFT, padx=8)

        # ── 状态栏 ──
        self.status_var = tk.StringVar(value="就绪")
        tk.Label(self.root, textvariable=self.status_var, font=FS,
                 bg=C["status_bg"], fg=C["status_fg"],
                 anchor=tk.W, padx=20, pady=6).pack(fill=tk.X, side=tk.BOTTOM)

        # ── 内容 ──
        body = tk.Frame(self.root, bg=C["bg"], padx=16, pady=12)
        body.pack(fill=tk.BOTH, expand=True)

        # ─── 链接卡片 ───
        c1_outer, c1 = card(body, "分享链接")
        c1_outer.pack(fill=tk.X, pady=(0, 8))
        row = tk.Frame(c1, bg=C["card"])
        row.pack(fill=tk.X)
        self.link_var = tk.StringVar()
        ent_frame, self.link_entry = self._input(row, font=FM, textvariable=self.link_var)
        ent_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.link_entry.bind("<Return>", lambda e: self._on_parse())
        self.parse_btn = RoundBtn(row, "解 析", C["primary"], C["primary_h"],
                                  cmd=self._on_parse, w=90, h=36)
        self.parse_btn.pack(side=tk.RIGHT)

        # ─── 信息卡片 ───
        c2_outer, c2 = card(body, "视频信息")
        c2_outer.pack(fill=tk.X, pady=(0, 8))
        info_border = tk.Frame(c2, bg=C["input_bd"], padx=1, pady=1)
        info_border.pack(fill=tk.X)
        self.info_text = tk.Text(
            info_border, height=3, font=FS, bg=C["list_bg"], fg=C["text"],
            relief=tk.FLAT, bd=0, highlightthickness=0,
            wrap=tk.WORD, padx=10, pady=8, state=tk.DISABLED
        )
        self.info_text.pack(fill=tk.X, padx=3, pady=3)

        # ─── 下载卡片 ───
        c3_outer, c3 = card(body, "下载")
        c3_outer.pack(fill=tk.X, pady=(0, 8))

        pr = tk.Frame(c3, bg=C["card"])
        pr.pack(fill=tk.X, pady=(0, 8))
        tk.Label(pr, text="保存到", font=FS, bg=C["card"], fg=C["text2"]).pack(side=tk.LEFT)
        self.path_var = tk.StringVar(value=self.download_dir)
        path_frame, _ = self._input(pr, font=FS, readonly=True, textvariable=self.path_var)
        path_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        RoundBtn(pr, "选择", C["gray"], C["gray_h"], cmd=self._choose_dir,
                 w=68, h=30, font=FS).pack(side=tk.RIGHT)

        self.progress = RoundBar(c3, h=10)
        self.progress.pack(fill=tk.X, pady=(0, 6))

        br = tk.Frame(c3, bg=C["card"])
        br.pack(fill=tk.X)
        self.progress_label = tk.Label(br, text="", font=FS, bg=C["card"], fg=C["text2"])
        self.progress_label.pack(side=tk.LEFT)
        self.dl_btn = RoundBtn(br, "下载视频", C["green"], C["green_h"],
                               cmd=self._on_download, w=110, h=36)
        self.dl_btn.pack(side=tk.RIGHT)

        # ─── 历史卡片（固定最小高度，可滚动） ───
        c4_outer, c4 = card(body, "下载记录")
        c4_outer.pack(fill=tk.BOTH, expand=True, pady=(0, 0))
        lf = tk.Frame(c4, bg=C["card"])
        lf.pack(fill=tk.BOTH, expand=True)
        lf.config(height=120)
        lf.pack_propagate(False)
        self.history_list = tk.Listbox(
            lf, font=FS, bg=C["list_bg"], fg=C["text"],
            relief=tk.FLAT, bd=0, highlightthickness=1,
            highlightbackground=C["input_bd"],
            selectbackground=C["list_sel"], selectforeground=C["text"],
            activestyle=tk.NONE)
        sb = tk.Scrollbar(lf, command=self.history_list.yview)
        self.history_list.configure(yscrollcommand=sb.set)
        self.history_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    # ── 设置信息文本 ──
    def _set_info(self, text):
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete("1.0", tk.END)
        self.info_text.insert("1.0", text)
        self.info_text.config(state=tk.DISABLED)

    # ── 业务逻辑 ──
    def _on_parse(self):
        link = self.link_var.get().strip()
        if not link:
            messagebox.showwarning("提示", "请先粘贴抖音分享链接")
            return
        self.parse_btn.set_enabled(False)
        self.dl_btn.set_enabled(False)
        self.current_video_info = None
        self._set_info("正在解析...")
        self.status_var.set("解析中...")

        def run():
            r = parse_douyin_link(link)
            self.root.after(0, lambda: self._parse_done(r))
        threading.Thread(target=run, daemon=True).start()

    def _parse_done(self, result):
        self.parse_btn.set_enabled(True)
        if result.get("success"):
            self.current_video_info = result
            t, a = result.get("title", "未知"), result.get("author", "未知")
            d = result.get("duration", 0)
            self._set_info(f"标题: {t}\n作者: {a}\n时长: {d // 1000}秒" if d else f"标题: {t}\n作者: {a}")
            self.status_var.set("解析成功")
            self.dl_btn.set_enabled(True)
        else:
            self._set_info(f"解析失败: {result.get('error', '未知错误')}")
            self.status_var.set("解析失败")

    def _choose_dir(self):
        p = filedialog.askdirectory(title="选择保存目录")
        if p:
            self.download_dir = p
            self.path_var.set(p)

    def _on_download(self):
        if not self.current_video_info:
            return
        url = self.current_video_info.get("video_url")
        if not url:
            messagebox.showerror("错误", "视频地址为空")
            return
        self.dl_btn.set_enabled(False)
        self.parse_btn.set_enabled(False)
        self.progress.set_value(0)
        self.progress_label.config(text="准备下载...")
        self.status_var.set("下载中...")
        title = self.current_video_info.get("title", "douyin_video")

        def cb(done, total):
            pct = done / total * 100 if total else 0
            self.root.after(0, lambda: self._prog(pct, done, total))
        def run():
            r = download_video(url, save_dir=self.path_var.get(),
                               filename=title, progress_callback=cb)
            self.root.after(0, lambda: self._dl_done(r, title))
        threading.Thread(target=run, daemon=True).start()

    def _prog(self, pct, done, total):
        self.progress.set_value(pct)
        self.progress_label.config(text=f"{done / 1048576:.1f} / {total / 1048576:.1f} MB  ({pct:.0f}%)")

    def _dl_done(self, result, title):
        self.parse_btn.set_enabled(True)
        if result.get("success"):
            fp, sz = result["path"], result["size"] / 1048576
            self.progress.set_value(100)
            self.progress_label.config(text=f"完成 — {sz:.1f} MB")
            self.status_var.set(f"已保存: {fp}")
            now = datetime.now().strftime("%H:%M:%S")
            fname = os.path.basename(fp)
            self.history_list.insert(tk.END, f"[{now}]  {title[:30]}  |  {sz:.1f}MB  →  {fname}")
            self.history_list.see(tk.END)
            messagebox.showinfo("完成", f"视频已保存:\n{fp}")
            self.dl_btn.set_enabled(True)
        else:
            self.progress_label.config(text="下载失败")
            self.status_var.set(f"失败: {result.get('error', '')}")
            messagebox.showerror("失败", result.get("error", "未知"))
            self.dl_btn.set_enabled(True)
