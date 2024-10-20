# (Yet Another) Kindle Weather Display

A framed e-Ink weather display built from a `Kindle Paperwhite 3 (7th Generation, 2015)`.

![photo](https://github.com/user-attachments/assets/6062ded0-b178-4c10-bf79-d50fd1f118e7)

## About the server

The UI is built using pure HTML/CSS and served as a rendered PNG to be displayed on the Kindle.

Uses free data from:

* tomorrow.io (current and future weather)
* open-meteo.com (air quality)
* MQTT (temperature sensors on my local network - you will need to modify this for your own usage)

Uses asyncio to decouple API calls from rendering the PNG.

### Manual deployment

```
export TOMORROW_IO_API_KEY=your_api_key
sudo apt install fonts-noto-core
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install webkit
python main.py --mock
```

### Docker deployment

Clone the repository and run:

```
export TOMORROW_IO_API_KEY=your_key; docker compose up -d --build dashboard-server
```

#### URL

Docker container serves rendered PNG at `http://localhost:4700/screenshot.png`

## Building the hardware

(I would have also considered the [inkplate-10](https://www.crowdsupply.com/soldered/inkplate-10)/[inkplate-6](https://www.crowdsupply.com/soldered/inkplate-6) had I known they existed)

1. Buy a used Kindle Paperwhite 3 (7th Generation, 2015). Make sure it is running firmware version 5.16.2.1.1 (or lower) so that it can be jailbroken.
2. Disassemble the Kindle ([ifixit guide](https://www.ifixit.com/Guide/Kindle+Paperwhite+3rd+Generation+Battery+Replacement/61550))
3. Buy a frame. I bought [this frame](https://www.amazon.com/dp/B003YN10M2?ref=ppx_yo2ov_dt_b_fed_asin_title) and it was a very tight squeeze, requiring some soldering because usb adaptors wouldn't fit. I recommend buying a 6"x8" frame instead.
4. Get a mat cut for the frame at a framing store. Dimensions of the screen are 4.75" x 3.5".
5. Glue the Kindle to the mat using something like Kwik Seal Adhesive Caulk.
6. Buy an angled USB connector, version AMRI-V8LE, so that you can plug in a power cable: [AliExpress](https://www.aliexpress.us/item/3256801306879430.html?spm=a2g0o.order_list.order_list_main.4.6faf1802ifd8ra&gatewayAdapt=glo2usa)
7. I bought a bigger 5000mAh battery ([link](https://www.amazon.com/dp/B08TTLBHSS?ref=ppx_yo2ov_dt_b_fed_asin_title)) so that I didn't need to charge it often. It's easy to unscrew the battery, remove the sticker, and clip the wires on the original battery. Keep all of the circuitry and the connector, and solder in the new battery leads. The battery I linked has its own safety circuitry.

## Jailbreaking the Kindle (updated October 2024)

1. Update the Kindle to version 5.16.2.1.1, if needed. Put `update_kindle_all_new_paperwhite_5.16.2.1.1.bin` in the root directory, and apply it from the settings menu.
2. Set the correct time in the Kindle settings and turn on airplane mode
3. Follow the [LanguageBreak](https://github.com/notmarek/LanguageBreak) instructions. For the Paperwhite 3, you'll need to install the hotfix _twice_ (see the LanguageBreak repo GitHub issues for more details).
4. Install MRPI using the MR Package Installer from [MobileRead](https://www.mobileread.com/forums/showthread.php?t=225030): copy the two folders to the root of the Kindle, then restart the Kindle.
5. Install KUAL: download the "coplate" version for the Paperwhite 3 from [MobileRead](https://www.mobileread.com/forums/showthread.php?t=225030). Put the KUAL.cfg in the “extensions” folder and `Update_KUALBooklet_f190a38_install.bin` file in the “mrpackages” folder (both folders were created during the MRPI install above). Type `;log mrpi` in the Kindle search box and press enter to trigger installation. 
6. Block automatic Kindle firmware updates by installing [BinaryRenamer](https://www.mobileread.com/forums/showthread.php?t=357438): copy the `BinaryRenamer` folder to the `extensions` directory. Eject the Kindle, open KUAL and run it. The device will restart.
7. Install the [Online screensaver extension](https://www.mobileread.com/forums/showthread.php?t=236104). Download from [this thread](https://github.com/Kuhno92/onlinescreensaverPW2). Copy the folder as `onlinescreensaver` to the `extensions` directory. Edit `onlinescreensaver/bin/config.sh` to point to your server: `IMAGE_URI="http://10.0.0.69:4700/screenshot.png"`.
8. Run KUAL from the Kindle Library and open the `Online-Screensaver` section
9. Test the one-time update. If it works, turn on "auto-download".

You're done! Your screensaver should show the dashboard.
