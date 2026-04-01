# LittleFS Desktop Manager
LittleFS Desktop Manager - Файловый менеджер на Python (Tkinter). Позволяет загружать, скачивать, удалять, переименовывать файлы и форматировать память LittleFS на микроконтроллерах (ESP8266/ESP32) прямо через COM-порт.

- **Полный функционал**: 
  - Загрузка в МК / Скачивание на ПК
  - Удаление / Переименование файлов
  - Форматирование файловой системы
  - Просмотр занятого/свободного места

## Установка и запуск
### Требования
- Python 3.8+
- Библиотека `pyserial`
### Установка зависимостей
 Откройте терминал и выполните:
```bash
pip install pyserial
```
### Запуск
```bash
python main.py
```
### Сборка в .exe (Для Windows)
 Установите PyInstaller:
```bash
pip install pyinstaller
```
 Соберите программу (замените icon.ico на название вашей иконки, если она есть):
```bash
pyinstaller --noconsole --onefile --icon=icon.ico main.py
```
 Готовый .exe файл появится в папке dist.
### Скачать
[LittleFS Desktop Manager](https://disk.yandex.ru/d/JeJ_uuZE3Uzd8A)
![screenshot_1](/doc/screenshot_1.jpg)
### Дополнительно
 Иконка взята с [icons8.com](https://icons8.ru/)

