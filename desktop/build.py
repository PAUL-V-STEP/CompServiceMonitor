"""
Скрипт сборки .exe файла для Windows
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path


def build_exe():
    """Собрать .exe файл"""
    print("=" * 60)
    print("🔨 СБОРКА DESKTOP ПРИЛОЖЕНИЯ")
    print("=" * 60)
    
    # Текущая директория
    current_dir = Path(__file__).parent
    
    # Проверяем наличие PyInstaller
    print("\n📦 Проверка PyInstaller...")
    try:
        import PyInstaller
        print(f"   ✓ PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("   ✗ PyInstaller не установлен")
        print("   Установка: pip install pyinstaller")
        sys.exit(1)
    
    # Имя приложения
    app_name = "CompServiceMonitor"
    
    # Параметры PyInstaller
    pyinstaller_args = [
        "pyinstaller",
        "--name", app_name,
        "--onefile",           # Один .exe файл
        "--windowed",          # Без консоли
        "--noconfirm",         # Перезаписывать без подтверждения
        "--clean",             # Очистить кеш
        
        # Иконка (если есть)
        # "--icon", "icon.ico",
        
        # Добавляем файлы
        "--add-data", f"styles.py{os.pathsep}.",
        "--add-data", f"api_client.py{os.pathsep}.",
        
        # Скрытые импорты
        "--hidden-import", "PyQt6",
        "--hidden-import", "PyQt6.QtCore",
        "--hidden-import", "PyQt6.QtWidgets",
        "--hidden-import", "PyQt6.QtGui",
        "--hidden-import", "requests",
        
        # Главный файл
        "main.py"
    ]
    
    print(f"\n🚀 Запуск сборки: {app_name}.exe")
    print("-" * 60)
    
    # Запускаем PyInstaller
    result = subprocess.run(pyinstaller_args, cwd=current_dir)
    
    if result.returncode == 0:
        exe_path = current_dir / "dist" / f"{app_name}.exe"
        
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print("\n" + "=" * 60)
            print("✅ СБОРКА ЗАВЕРШЕНА УСПЕШНО!")
            print("=" * 60)
            print(f"\n📁 Файл: {exe_path}")
            print(f"📊 Размер: {size_mb:.1f} MB")
            print("\n💡 Для запуска:")
            print(f"   1. Запустите backend: python run.py")
            print(f"   2. Запустите {app_name}.exe")
        else:
            print("\n❌ Ошибка: .exe файл не найден")
    else:
        print("\n❌ Ошибка сборки")
        sys.exit(1)


def clean():
    """Очистить артефакты сборки"""
    current_dir = Path(__file__).parent
    
    dirs_to_remove = ["build", "dist", "__pycache__"]
    files_to_remove = ["*.spec"]
    
    print("🧹 Очистка артефактов сборки...")
    
    for dir_name in dirs_to_remove:
        dir_path = current_dir / dir_name
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"   Удалено: {dir_name}/")
    
    for pattern in files_to_remove:
        for file in current_dir.glob(pattern):
            file.unlink()
            print(f"   Удалено: {file.name}")
    
    print("✓ Очистка завершена")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        clean()
    else:
        build_exe()

