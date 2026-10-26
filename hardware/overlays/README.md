# Orange Pi Zero 2W: сохранённые overlays

`original/` содержит четыре исходных DTBO с SD-карты и их декомпилированные DTS.
SHA-256 каждого файла указан в `original/sha256.json`. Это архив состояния,
а не набор overlays для одновременного включения.

`opi-zero2w-spi1-cs0-cs1.dts` — кандидат исправления активного
`spidev_spi1_cs0_cs1`: он явно включает pinmux PH5 (CS0) и PH9 (CS1),
сохраняя SPI1 и логические CS0/CS1. `spi1-cs0-cs1.patch` показывает отличие
от декомпилированного оригинала; патч также содержит нормализацию DTS.

Проверено офлайн на DTB `6.12.47-current-sunxi64`: компиляция и наложение,
две группы CS в итоговом pinctrl. Физический обмен пока не проверен.
После обновления ядра проверку нужно повторить на **новом DTB**:

```sh
dtc -@ -I dts -O dtb -o /tmp/opi-zero2w-spi1-cs0-cs1.dtbo opi-zero2w-spi1-cs0-cs1.dts
fdtoverlay -i /boot/dtb/allwinner/sun50i-h618-orangepi-zero2w.dtb \
  -o /tmp/opi-zero2w-merged.dtb /tmp/opi-zero2w-spi1-cs0-cs1.dtbo
```

Установка на работающей Orange Pi, после проверки распиновки:

```sh
sudo install -m 0644 /tmp/opi-zero2w-spi1-cs0-cs1.dtbo /boot/overlay-user/
```

В существующей строке `user_overlays` заменить только старый токен
`spidev_spi1_cs0_cs1` на `opi-zero2w-spi1-cs0-cs1`, сохранив другие
неконфликтующие overlays. Не заменять весь `armbianEnv.txt` копией из архива:
UUID корневого раздела и параметры нового образа должны остаться его собственными.

Ограничения архива:

- `spidev_spi1_cs2_pi3_cs3_pi4` фактически занимает CS0/CS1 через PI3/PI4.
  Совместно с native-CS overlay даёт повторяющиеся адреса устройств.
- `spidev_spi1_cs4_pi3` описывает CS0–CS3, а не CS4.
- `sun50i-h616-usb0-host` меняет USB0 в host; это несовместимо с использованием
  того же порта как USB gadget.
- Исправленный кандидат по-прежнему не создаёт CS2 для PN532.

На исходную SD-карту при подготовке архива ничего не записывалось.
