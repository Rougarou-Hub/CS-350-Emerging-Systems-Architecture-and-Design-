from time import sleep
from datetime import datetime
from statemachine import StateMachine, State
import board
import adafruit_ahtx0
import digitalio
import adafruit_character_lcd.character_lcd as characterlcd
import serial
from gpiozero import Button, PWMLED
from threading import Thread
from math import floor

DEBUG = True

i2c = board.I2C()
thSensor = adafruit_ahtx0.AHTx0(i2c)

ser = serial.Serial(
        port='/dev/ttyS0',
        baudrate = 115200,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS,
        timeout=1
)

redLight = PWMLED(18)
blueLight = PWMLED(23)

class ManagedDisplay():
    def __init__(self):
        self.lcd_rs = digitalio.DigitalInOut(board.D17)
        self.lcd_en = digitalio.DigitalInOut(board.D27)
        self.lcd_d4 = digitalio.DigitalInOut(board.D5)
        self.lcd_d5 = digitalio.DigitalInOut(board.D6)
        self.lcd_d6 = digitalio.DigitalInOut(board.D13)
        self.lcd_d7 = digitalio.DigitalInOut(board.D26)

        self.lcd_columns = 16
        self.lcd_rows = 2 

        self.lcd = characterlcd.Character_LCD_Mono(
            self.lcd_rs, self.lcd_en, 
            self.lcd_d4, self.lcd_d5, self.lcd_d6, self.lcd_d7, 
            self.lcd_columns, self.lcd_rows
        )
        self.lcd.clear()

    def cleanupDisplay(self):
        self.lcd.clear()
        self.lcd_rs.deinit()
        self.lcd_en.deinit()
        self.lcd_d4.deinit()
        self.lcd_d5.deinit()
        self.lcd_d6.deinit()
        self.lcd_d7.deinit()
        
    def clear(self):
        self.lcd.clear()

    def updateScreen(self, message):
        self.lcd.clear()
        self.lcd.message = message

screen = ManagedDisplay()

class TemperatureMachine(StateMachine):
    off = State(initial = True)
    heat = State()
    cool = State()

    setPoint = 72

    cycle = (
        off.to(heat) |
        heat.to(cool) |
        cool.to(off)
    )

    def on_enter_heat(self):
        self.updateLights()
        if(DEBUG):
            print("* Changing state to heat")

    def on_exit_heat(self):
        redLight.off()

    def on_enter_cool(self):
        self.updateLights()
        if(DEBUG):
            print("* Changing state to cool")
    
    def on_exit_cool(self):
        blueLight.off()

    def on_enter_off(self):
        redLight.off()
        blueLight.off()
        if(DEBUG):
            print("* Changing state to off")
    
    def processTempStateButton(self):
        if(DEBUG):
            print("Cycling Temperature State")
        self.cycle()

    def processTempIncButton(self):
        if(DEBUG):
            print("Increasing Set Point")
        self.setPoint += 1
        self.updateLights()

    def processTempDecButton(self):
        if(DEBUG):
            print("Decreasing Set Point")
        self.setPoint -= 1
        self.updateLights()

    def updateLights(self):
        temp = floor(self.getFahrenheit())
        redLight.off()
        blueLight.off()
    
        if(DEBUG):
            print(f"State: {self.current_state.id}")
            print(f"SetPoint: {self.setPoint}")
            print(f"Temp: {temp}")

        if self.current_state.id == "off":
            return

        if self.current_state.id == "heat":
            if temp < self.setPoint:
                redLight.pulse()
            else:
                redLight.on()

        if self.current_state.id == "cool":
            if temp > self.setPoint:
                blueLight.pulse()
            else:
                blueLight.on()

    def run(self):
        myThread = Thread(target=self.manageMyDisplay)
        myThread.start()

    def getFahrenheit(self):
        t = thSensor.temperature
        return (((9/5) * t) + 32)
    
    def setupSerialOutput(self):
        output = f"{self.current_state.id},{floor(self.getFahrenheit())},{self.setPoint}\n"
        return output
    
    endDisplay = False

    def manageMyDisplay(self):
        counter = 1
        altCounter = 1
        while not self.endDisplay:
            if(DEBUG):
                print("Processing Display Info...")
    
            current_time = datetime.now()
    
            lcd_line_1 = current_time.strftime("%m/%d %H:%M") + "\n"
    
            if(altCounter < 6):
                lcd_line_2 = f"Temp: {floor(self.getFahrenheit())}F"
                altCounter = altCounter + 1
            else:
                lcd_line_2 = f"{self.current_state.id}:{self.setPoint}F"
                altCounter = altCounter + 1
                if(altCounter >= 11):
                    self.updateLights()
                    altCounter = 1
    
            screen.updateScreen(lcd_line_1 + lcd_line_2)
    
            if(DEBUG):
               print(f"Counter: {counter}")
            if((counter % 30) == 0):
                ser.write(self.setupSerialOutput().encode())
                counter = 1
            else:
                counter = counter + 1
            sleep(1)

        screen.cleanupDisplay()

tsm = TemperatureMachine()
tsm.run()

greenButton = Button(24)
greenButton.when_pressed = tsm.processTempStateButton

redButton = Button(25)
redButton.when_pressed = tsm.processTempIncButton

blueButton = Button(12)
blueButton.when_pressed = tsm.processTempDecButton

repeat = True

while repeat:
    try:
        sleep(30)
    except KeyboardInterrupt:
        print("Cleaning up. Exiting...")
        repeat = False
        tsm.endDisplay = True
        sleep(1)
