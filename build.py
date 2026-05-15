"""一键打包为 exe（带图标）。"""
import subprocess, shutil, os

NAME = "抖音去水印"
ICON = "icon.ico"

for d in ("build", "dist"):
    if os.path.exists(d):
        shutil.rmtree(d)

subprocess.run([
    "pyinstaller", "--onefile", "--windowed", "--clean",
    "--icon", ICON, "--name", NAME, "main.py",
], check=True)

src = os.path.join("dist", f"{NAME}.exe")
if not os.path.exists(src):
    print("Build failed!")
    exit(1)

dst = f"{NAME}.exe"
tmp = "_tmp.exe"
shutil.copy2(src, tmp)
shutil.rmtree("build", ignore_errors=True)
shutil.rmtree("dist", ignore_errors=True)
if os.path.exists(dst):
    os.replace(tmp, dst)
else:
    os.rename(tmp, dst)

size_mb = os.path.getsize(dst) / 1048576
print(f"\nDone: {dst} ({size_mb:.1f} MB)")
