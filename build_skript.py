#!/usr/bin/env python3
import argparse
import os
import platform
import shutil
import subprocess
import sys

from pathlib import Path

STDS      = ["11", "14", "17", "20", "23"]
CONFIGS   = ["Debug", "Release"]
SHARED    = ["ON", "OFF"]
JOBS      = os.cpu_count() or 4

# -----------------------------------------------------------------------------
def detect_compilers():
    found = []
    system = platform.system()

    # Clang
    clang = shutil.which("clang++")
    if clang:
        cc = shutil.which("clang")
        found.append(("clang", cc or "clang", clang, "Clang"))

    # GCC
    gcc = shutil.which("g++")
    if gcc:
        cc = shutil.which("gcc")
        found.append(("gcc", cc or "gcc", gcc, "GCC"))

    # MinGW (Windows / кросс на Linux)
    mingw = shutil.which("x86_64-w64-mingw32-g++")
    if mingw:
        found.append(("mingw", "x86_64-w64-mingw32-gcc", mingw, "MinGW64"))

    mingw32 = shutil.which("mingw32-g++")
    if mingw32 and not any(c[0] == "mingw" for c in found):
        found.append(("mingw32", "mingw32-gcc", mingw32, "MinGW32"))

    # MSVC (только Windows, ищем cl в PATH)
    if system == "Windows" and shutil.which("cl"):
        found.append(("msvc", "cl", "cl", "MSVC"))

    # Intel oneAPI
    icx = shutil.which("icpx")
    if icx:
        found.append(("icx", "icx", "icpx", "Intel oneAPI"))

    # Intel Classic
    icc = shutil.which("icpc")
    if icc:
        found.append(("icc", "icc", "icpc", "Intel Classic"))

    return found

# -----------------------------------------------------------------------------
def select_generator(compiler_key):
    # Ninja в приоритете
    if shutil.which("ninja"):
        return ("ninja", "Ninja")

    system = platform.system()
    if system == "Windows":
        if compiler_key == "msvc":
            vs = os.environ.get("CMAKE_VS_GENERATOR", "Visual Studio 18")
            return ("msvc", vs)
        return ("mingw", "MinGW Makefiles")

    # Linux / macOS
    if shutil.which("make"):
        return ("make", "Unix Makefiles")
    return ("ninja", "Ninja")

# -----------------------------------------------------------------------------
def run(cmd: list[str], cwd: Path):
    print(">>> " + " ".join(str(c) for c in cmd))
    r = subprocess.run(cmd, cwd=cwd)
    if r.returncode:
        sys.exit(r.returncode)

def build(src, dst, shared, std, cfg, comp_key, comp_c, comp_cxx, gen_name, gen_id):
    out = dst / f"{'shared' if shared == 'ON' else 'static'}" / f"{gen_name}-{comp_key.upper()}" / cfg / f"std{std}"
    # if "Visual Studio" not in gen_id:
    #     out = out / cfg.lower()
    out.mkdir(parents=True, exist_ok=True)

    cmake_args = [
        "cmake", str(src),
        "-G", gen_id,
        f"-DCMAKE_CXX_STANDARD={std}",
        "-DCMAKE_CXX_STANDARD_REQUIRED=ON",
        f"-DCMAKE_C_COMPILER={comp_c}",
        f"-DCMAKE_CXX_COMPILER={comp_cxx}",
        f"-DBUILD_SHARED_LIBS={shared}"
    ]

    if "Visual Studio" in gen_id:
        cmake_args += ["-A", "x64"]

    if "Visual Studio" not in gen_id:
        cmake_args += [f"-DCMAKE_BUILD_TYPE={cfg}"]

    run(cmake_args, out)

    build_cmd = ["cmake", "--build", str(out)]
    if "Visual Studio" in gen_id:
        build_cmd += ["--config", cfg]
    build_cmd += ["-j", str(JOBS)]

    run(build_cmd, out)
    print(f"  [OK] {comp_key} C++{std} {cfg} -> {out}")

# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Сборка: все компиляторы × C++11..23 × Debug/Release")
    parser.add_argument("--path",  help="Путь к cmake.txt файлу")
    parser.add_argument("--build", type=str, default=None, help="Путь для сборки")
    parser.add_argument("--shared",nargs="+", choices=SHARED, default=SHARED, help="DLL (shared library), or LIB (static library)")
    parser.add_argument("--comp",  default="auto", help="Компилятор: auto, msvc, gcc, clang, mingw...")
    parser.add_argument("--std",   nargs="+", choices=STDS, default=STDS)
    parser.add_argument("--cfg",   nargs="+", choices=CONFIGS, default=CONFIGS)
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    cmake_file = Path(args.path)

    if args.build is None:
        target_dir = cmake_file.parent / "build"
    else:
        target_dir = Path(args.build)

    compilers = detect_compilers()
    if not compilers:
        print("Компилятор не найден. Проверьте PATH (g++, clang++, cl)")
        sys.exit(1)

    if args.comp != "auto":
        compilers = [c for c in compilers if c[0] == args.comp]
        if not compilers:
            print(f"Компилятор '{args.comp}' не найден")
            sys.exit(1)

    for comp_key, comp_c, comp_cxx, desc in compilers:
        gen_name, gen_id = select_generator(comp_key)
        print(f"\n{'='*50}")
        print(f"{comp_key} ({desc}) | генератор: {gen_name}")
        print(f"{'='*50}")
        for shared in args.shared:
            for std in args.std:
                for cfg in args.cfg:
                    build(cmake_file, target_dir, shared, std, cfg, comp_key, comp_c, comp_cxx, gen_name, gen_id)

    print("\nГотово.")

if __name__ == "__main__":
    main()

# Авто: все найденные компиляторы
#python build.py

# Только GCC
#python build.py --comp gcc --std 17 20 --cfg Release

# С чисткой
#python build.py --clean

# Только Clang + C++20 + Debug
#python build.py --comp clang --std 20 --cfg Debug