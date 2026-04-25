# Noto Sans SC (embeddable TTF for ReportLab)

These files are **Noto Sans SC** (Google Fonts / OFL), suitable for Simplified Chinese body text in ReportLab.

| File | Weight | Source |
|------|--------|--------|
| `NotoSansSC-Regular.ttf` | 400 | [Google Fonts](https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;700) → `fonts.gstatic.com` TTF |
| `NotoSansSC-Bold.ttf` | 700 | same |

**License:** SIL Open Font License 1.1 (OFL).

**Fenced code (Noto Sans Mono):** not stored under this folder. `register_mono_font()` **first** looks for **NotoSansMono-Regular.ttf** in OS font paths (Linux `…/noto/`, Homebrew, macOS `~/Library/Fonts` / `/Library/Fonts/`, `C:\Windows\Fonts\`, etc.), then Menlo/Consolas/DejaVu, else **Courier**. To install the OFL TTF, use your OS or [Google Fonts](https://fonts.google.com/noto/specimen/Noto+Sans+Mono) / package managers (`fonts-noto` on some Linux distros).

**Re-download** (if `NotoSansSC-*.ttf` missing):

```bash
cd .cursor/skills/md-to-pdf/fonts
curl -fsSL -o NotoSansSC-Regular.ttf "https://fonts.gstatic.com/s/notosanssc/v40/k3kCo84MPvpLmixcA63oeAL7Iqp5IZJF9bmaG9_FnYw.ttf"
curl -fsSL -o NotoSansSC-Bold.ttf "https://fonts.gstatic.com/s/notosanssc/v40/k3kCo84MPvpLmixcA63oeAL7Iqp5IZJF9bmaGzjCnYw.ttf"
```

If Google changes paths, get current TTF URLs from `https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;700` (with a browser User-Agent).

**Repository:** 将 `NotoSansSC-Regular.ttf` 与 `NotoSansSC-Bold.ttf` **纳入 Git**（本仓库不提交 zip 包），以便克隆即可渲染（正文 + 页眉/页脚 + Mermaid 共用）。

**Offline recovery (no zip in repo):** 误删 TTF 时用 **`git restore`** / 从其他机器复制同文件 / 有网络时按上文 curl 重下。可选：在本地 `fonts/` 自行放入 **`noto_sans_sc_bundled.zip`**（内容与两个 TTF 相同），`register_fonts()` 会在 TTF 缺失时**自动**从该 zip 还原（不提交到版本库也可）。

**Size:** ~10 MB each. 大文件可配合 Git LFS，按团队规范。

**误删/缺失时的提示:** 无可用 CJK 嵌入字体会 **退出并打印** 说明；**不能** 用纯西文内置字体代替，否则中文缺字。
