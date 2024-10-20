import os
import argparse
import json
import time
import asyncio
import aiohttp
import aiomqtt
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from playwright.async_api import async_playwright, Route
from jinja2 import Environment, FileSystemLoader
from PIL import Image
from io import BytesIO
import ephem

tomorrow_io_api_key = os.getenv('TOMORROW_IO_API_KEY', '')
www_dir = os.getenv('WWW_DIR', os.getcwd())
measurements = {} # {key => [timestamp, last_value]}

# Check for mock mode argument
parser = argparse.ArgumentParser(description="Generate screenshots for the Kindle dashboard.")
parser.add_argument('--mock', action='store_true', help="Enable mock API mode.")
args = parser.parse_args()
is_mock_mode = args.mock
if is_mock_mode:
    print('Running in mock APIs mode 🤖')
elif tomorrow_io_api_key == '':
    print('⚠️  WARNING: no tomorrow.io API key')

weather_codes = {
    0: "Unknown",
    1000: "Clear, Sunny",
    1100: "Mostly Clear",
    1101: "Partly Cloudy",
    1102: "Mostly Cloudy",
    1001: "Cloudy",
    2000: "Fog",
    2100: "Light Fog",
    4000: "Drizzle",
    4001: "Rain",
    4200: "Light Rain",
    4201: "Heavy Rain",
    5000: "Snow",
    5001: "Flurries",
    5100: "Light Snow",
    5101: "Heavy Snow",
    6000: "Freezing Rain",
    6001: "Freezing Rain",
    6200: "Freezing Rain",
    6201: "Freezing Rain",
    7000: "Ice Pellets",
    7101: "Ice Pellets",
    7102: "Ice Pellets",
    8000: "Thunderstorm" }

def save_image(buffer):
    # Converts to greyscale colorspace before saving
    # Kindles don't display RGB images correctly
    img = Image.open(BytesIO(buffer)).rotate(-90, expand=True).convert('L')
    img.save(f'{www_dir}/screenshot.out.png')
    os.rename(f'{www_dir}/screenshot.out.png', f'{www_dir}/screenshot.png')

async def generate_screenshot(browser, html):
    if is_mock_mode:
        with open('debug.html', 'w') as f:
            f.write(html.replace("http://localhost/",""))

    context = await browser.new_context(java_script_enabled=False)
    page = await context.new_page()
    await page.set_viewport_size({"width": 1448, "height": 1072})

    # Intercept image loading
    async def handle(route: Route):
        path = route.request.url.replace("http://localhost/","")
        await route.fulfill(path=path)
    await page.route("**/images/*.png", handle)
    await page.route("**/images/weather/*.png", handle)

    await page.set_content(html)
    buffer = await page.screenshot()
    await context.close()

    # Save image in a different thread
    await asyncio.to_thread(save_image, buffer)

def get_basement_temps():
    temps = {
        'high': '--',
        'low': '--',
        'current': '--' }

    if 'basement_temp' in measurements:
        timestamp, temp_value = measurements['basement_temp']
        if time.time() - timestamp > 10*60: # 10 minutes
            temps['current'] = '--'
        else:
            temps['current'] = f'{float(temp_value):.0f}'

    if 'basement_high' in measurements:
        timestamp, temp_value = measurements['basement_high']
        if time.time() - timestamp > 60*60*24: # 24 hours
            temps['high'] = '--'
        else:
            temps['high'] = f'{float(temp_value):.0f}'

    if 'basement_low' in measurements:
        timestamp, temp_value = measurements['basement_low']
        if time.time() - timestamp > 60*60*24: # 24 hours
            temps['low'] = '--'
        else:
            temps['low'] = f'{float(temp_value):.0f}'

    return temps

def get_nursery_temps():
    temps = {
        'high': '--',
        'low': '--',
        'current': '--' }

    if 'nursery_temp' in measurements:
        timestamp, temp_value = measurements['nursery_temp']
        if time.time() - timestamp > 10*60: # 10 minutes
            temps['current'] = '--'
        else:
            temps['current'] = f'{(float(temp_value) * 9/5) + 32:.0f}'

    if 'nursery_high' in measurements:
        timestamp, temp_value = measurements['nursery_high']
        if time.time() - timestamp > 60*60*24: # 24 hours
            temps['high'] = '--'
        else:
            temps['high'] = f'{(float(temp_value) * 9/5) + 32:.0f}'

    if 'nursery_low' in measurements:
        timestamp, temp_value = measurements['nursery_low']
        if time.time() - timestamp > 60*60*24: # 24 hours
            temps['low'] = '--'
        else:
            temps['low'] = f'{(float(temp_value) * 9/5) + 32:.0f}'

    return temps

def get_aqi_value():
    if 'aqi' not in measurements:
        return "n/a"

    timestamp, aqi_value = measurements['aqi']
    if time.time() - timestamp > 15*60:
        return "n/a"
    else:
        return aqi_value

def graph_range(values):
    high = float(max(values))
    low = float(min(values))
    mid = low + ((high - low) / 2)

    # At minimum, a range of 20 degrees
    graph_max = mid + 10
    graph_min = mid - 10

    if high > graph_max:
        graph_max = high
    if low < graph_min:
        graph_min = low

    return [graph_min, graph_max]

def is_dark(when=None):
    seattle = ephem.city("Seattle")
    sun = ephem.Sun()
    if when:
        seattle.date = when
    return seattle.previous_setting(sun) > seattle.previous_rising(sun)

def get_weather_values():
    weather = {
        'current_temperature': "--",
        'current_weather_code': 0,
        'current_weather_str': "--",
        'is_dark': False,
        'daily_high': "--",
        'daily_low': "--",
        'graph_min': 0,
        'graph_max': 100,
        'forecast': []}

    if 'weather_current' not in measurements or 'weather_forecast' not in measurements:
        return weather

    weather['is_dark'] = is_dark()

    timestamp, weather_current = measurements['weather_current']
    if time.time() - timestamp < 35*60:
        weather['current_temperature'] = f'{weather_current["data"]["values"]["temperature"]:.0f}'
        weather['current_weather_code'] = weather_current["data"]["values"]["weatherCode"]
        weather['current_weather_str'] = weather_codes[weather_current["data"]["values"]["weatherCode"]]
        if weather['is_dark'] and weather['current_weather_code'] == 1000:
            weather['current_weather_str'] = "Clear"

    timestamp, weather_forecast = measurements['weather_forecast']
    if time.time() - timestamp < 35*60:
        weather['daily_high'] = f'{weather_forecast["timelines"]["daily"][0]["values"]["temperatureMax"]:.0f}'
        weather['daily_low'] = f'{weather_forecast["timelines"]["daily"][0]["values"]["temperatureMin"]:.0f}'

        # Hourly forecast
        hourly = weather_forecast["timelines"]["hourly"]
        temps = []
        for i in range(0, 12):
            weather['forecast'].append({
                'hour': datetime.fromisoformat(hourly[i]['time'].replace("Z", "+00:00")).astimezone(ZoneInfo("America/Los_Angeles")).strftime("%-I %p"),
                'temperature': hourly[i]["values"]["temperature"],
                'weather_code': hourly[i]['values']['weatherCode'],
                'precipitation_probability': hourly[i]['values']['precipitationProbability'],
                'is_dark': is_dark(datetime.fromisoformat(hourly[i]["time"]))
                })
            temps.append(hourly[i]["values"]["temperature"])

        # Graph min / max
        weather['graph_min'], weather['graph_max'] = graph_range(temps)

    return weather

async def task_get_weather():
    global measurements
    url_current = 'https://api.tomorrow.io/v4/weather/realtime?units=imperial&location=98103&apikey=' + tomorrow_io_api_key
    url_forecast = 'https://api.tomorrow.io/v4/weather/forecast?units=imperial&location=98103&apikey=' + tomorrow_io_api_key

    if is_mock_mode:
        with open('mock/weather_current.json') as f:
            measurements['weather_current'] = [time.time(), json.load(f)]
        with open('mock/weather_forecast.json') as f:
            measurements['weather_forecast'] = [time.time(), json.load(f)]
        return

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url_current) as response:
                    if response.status != 200:
                        raise Exception("non-200 response from current weather API")
                    body = await response.text()
                    weather = json.loads(body)
                    measurements['weather_current'] = [time.time(), weather]
                async with session.get(url_forecast) as response:
                    if response.status != 200:
                        raise Exception("non-200 response from weather forecast API")
                    body = await response.text()
                    weather = json.loads(body)
                    measurements['weather_forecast'] = [time.time(), weather]
        except Exception as e:
            print(("Failed to get weather. Error: " + repr(e)))
        finally:
            await asyncio.sleep(60*10) # 10 minutes

async def task_get_aqi():
    global measurements
    url = 'http://air-quality-api.open-meteo.com/v1/air-quality?latitude=47.677696&longitude=-122.351851&current=us_aqi&hourly=us_aqi&forecast_days=1'

    if is_mock_mode:
        with open('mock/aqi.json') as f:
            measurements['aqi'] = [time.time(), json.load(f)['current']['us_aqi']]
        return

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise Exception("non-200 response from AQI API")
                    body = await response.text()
                    aqi = json.loads(body)['current']['us_aqi']
                    measurements['aqi'] = [time.time(), aqi]
        except Exception as e:
            print(("Failed to get AQI. Error: " + repr(e)))
        finally:
            await asyncio.sleep(60*10) # 10 minutes

async def task_screenshots(template):
    # Pause to make debugging easier
    if is_mock_mode:
        await asyncio.sleep(1) # 1 second
    else:
        await asyncio.sleep(3) # 3 seconds

    async with async_playwright() as playwright:
        browser = await playwright.webkit.launch()

        while True:
            try:
                weather = get_weather_values()
                nursery = get_nursery_temps() 
                basement = get_basement_temps() 

                # Render template
                context = {
                    'weather_description': weather['current_weather_str'],
                    'weather_code': weather['current_weather_code'],
                    'current_date': datetime.now(ZoneInfo('America/Los_Angeles')).strftime('%A, %B %-d'),
                    'current_temp': weather['current_temperature'],
                    'is_dark': weather['is_dark'],
                    'daily_temp_high': weather['daily_high'],
                    'daily_temp_low': weather['daily_low'],
                    'forecast': weather['forecast'],
                    'graph_min': weather['graph_min'],
                    'graph_max': weather['graph_max'],
                    'nursery_temp': nursery['current'],
                    'nursery_temp_high': nursery['high'],
                    'nursery_temp_low': nursery['low'],
                    'aqi': get_aqi_value(),
                    'last_refreshed_timestamp': datetime.now(ZoneInfo("America/Los_Angeles")).strftime('%-I:%M %p'),
                    'basement_temp': basement['current'],
                    'basement_temp_high': basement['high'],
                    'basement_temp_low': basement['low']
                }
                html = await template.render_async(context)

                # Run Playwright
                await generate_screenshot(browser, html)

                # Yield
                print('Generated screenshot; sleeping 🥱')
                await asyncio.sleep(60) # 1 minute
            except Exception as e:
                print(f"An unexpected error occurred in the screenshot task: {e}")
                await asyncio.sleep(60) # 1 minute

async def task_mqtt_listener():
    global measurements
    client = aiomqtt.Client("10.0.0.69")
    interval = 5  # Seconds

    if is_mock_mode:
        measurements['nursery_temp'] = [time.time(), 19.4] 
        measurements['nursery_low'] = [time.time(), 18.2] 
        measurements['nursery_high'] = [time.time(), 20.2] 
        measurements['basement_temp'] = [time.time(), 66.1] 
        measurements['basement_low'] = [time.time(), 65.5] 
        measurements['basement_high'] = [time.time(), 67.0] 
        return

    while True:
        try:
            async with client:
                await client.subscribe("temperature-tmp102/sensor/temperature_sensor/state") # degrees C
                await client.subscribe("temperature-sht41/sensor/sht41_temperature/state") # degrees F
                async for message in client.messages:
                    try:
                        if 'tmp102' in message.topic.value:
                            # Current temperature
                            temperature = message.payload.decode("ascii")
                            measurements['nursery_temp'] = [time.time(), temperature]

                            # Delete high/low keys if it's a new calendar day
                            calendar_day = datetime.fromtimestamp(time.time(), ZoneInfo('America/Los_Angeles')).day
                            if 'nursery_high' in measurements:
                                if calendar_day != datetime.fromtimestamp(measurements['nursery_high'][0], ZoneInfo('America/Los_Angeles')).day:
                                    del measurements['nursery_high']
                            if 'nursery_low' in measurements:
                                if calendar_day != datetime.fromtimestamp(measurements['nursery_low'][0], ZoneInfo('America/Los_Angeles')).day:
                                    del measurements['nursery_low']

                            # Record high/low
                            if 'nursery_high' not in measurements or temperature > measurements['nursery_high'][1]:
                                measurements['nursery_high'] = [time.time(), temperature]
                            if 'nursery_low' not in measurements or temperature < measurements['nursery_low'][1]:
                                measurements['nursery_low'] = [time.time(), temperature]
                        elif 'sht41' in message.topic.value:
                            # Current temperature
                            temperature = message.payload.decode("ascii")
                            measurements['basement_temp'] = [time.time(), temperature]

                            # Delete high/low keys if it's a new calendar day
                            calendar_day = datetime.fromtimestamp(time.time(), ZoneInfo('America/Los_Angeles')).day
                            if 'basement_high' in measurements:
                                if calendar_day != datetime.fromtimestamp(measurements['basement_high'][0], ZoneInfo('America/Los_Angeles')).day:
                                    del measurements['basement_high']
                            if 'basement_low' in measurements:
                                if calendar_day != datetime.fromtimestamp(measurements['basement_low'][0], ZoneInfo('America/Los_Angeles')).day:
                                    del measurements['basement_low']

                            # Record high/low
                            if 'basement_high' not in measurements or temperature > measurements['basement_high'][1]:
                                measurements['basement_high'] = [time.time(), temperature]
                            if 'basement_low' not in measurements or temperature < measurements['basement_low'][1]:
                                measurements['basement_low'] = [time.time(), temperature]

                    except Exception as e:
                        print(("Failed to handle MQTT message. Error: " + repr(e)))
        except aiomqtt.MqttError:
            print(f"Connection lost; Reconnecting in {interval} seconds ...")
            await asyncio.sleep(interval)
        except Exception as e:
            print(f"An unexpected error occurred in the MQTT task: {e}")
            await asyncio.sleep(60) # 1 minute

# Load the dashboard template
file_loader = FileSystemLoader(os.getcwd())
env = Environment(loader=file_loader, enable_async=True)
template = env.get_template('template.html')

# Run
async def main():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(task_screenshots(template))
        tg.create_task(task_mqtt_listener())
        tg.create_task(task_get_aqi())
        tg.create_task(task_get_weather())

asyncio.run(main())
