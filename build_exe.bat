@echo off
echo Building LoLTracker.exe...
echo This may take a minute.

:: Убедись, что PyInstaller установлен
pip install pyinstaller

:: Запуск сборки
:: --noconsole: Не показывать черное окно
:: --onefile: Собрать все в один exe
:: --add-data: Запихнуть папку assets внутрь exe (формат windows: папка;папка)
:: --name: Имя файла
:: --icon: Иконка самого файла (используем Флеш как заглушку, но в идеале нужен .ico)

pyinstaller --noconsole --onefile --name "LoLTracker" --add-data "assets;assets" main.py

echo.
echo Build Complete!
echo You can find your app in the "dist" folder.
pause