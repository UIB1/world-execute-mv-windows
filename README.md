# world.execute(me); — Windows 终端版

在 Windows 终端中播放 Mili《world.execute(me);》的字符动画。动画和中英字幕随音频时间同步，默认音量为 30%。

## 播放

从 [Releases](https://github.com/UIB1/world-execute-mv-windows/releases/latest) 下载 `world-execute-mv-windows-terminal.zip`，完整解压后双击 `play.cmd`，或在解压目录执行以下命令。

```powershell
.\play.cmd
```

适用于 Windows 10/11 x64。发布包内置 Python 运行时，可以离线播放。按空格开始或暂停，按方向键前进或后退 5 秒，按数字键 1–5 跳转章节，按 Q 退出。建议将终端最大化，快捷键详情可在播放时按 H 查看。

## 构建

使用 Windows x64 上的完整 CPython 3.12 安装和系统自带的 .NET Framework C# 编译器。向构建脚本传入本地 MP3 文件的路径。

```powershell
py -3.12 .\build.py 'C:\path\to\song.mp3'
```

构建输出为 `dist/world-execute-mv-windows-terminal.zip`。若使用其他音频，中英字幕和动画时序仍以原曲为准。

## 来源

字符动画、字幕和频谱数据来自上游项目 [world.execute-me-ascii](https://github.com/yym8224961/world.execute-me-ascii)。原曲与歌词为 Mili《world.execute(me);》。
