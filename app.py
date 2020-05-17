#Libraries imported
import RPi.GPIO as GPIO
from flask import Flask, render_template, request,Response, redirect, url_for, jsonify,copy_current_request_context
from flask_socketio import SocketIO, emit
from threading import Thread, Event
import signal 
import logging
import sys
import time
import Adafruit_BMP.BMP085 as BMP085
import fingerprint_test #Runs fingerprint_test from different script

import hashlib
import paho.mqtt.client as mqtt


GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

GPIO.cleanup()
GPIO.setup(17, GPIO.OUT)
GPIO.output(17, GPIO.HIGH)
# Raspberry Pi camera module
from camera_pi import Camera

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
app.config['DEBUG'] = True

#This turns the flask application into a socketio app which allows the webpage to be ran and data to be loaded
socketio = SocketIO(app, async_mode=None, logger=True, engineio_logger=True)
#This is the random number generator
thread = Thread()
thread_stop_event = Event()

BMPSensor = BMP085.BMP085() #SCL pin is on GPIO 2 (SCL) and SDA is on GPIO 2 (SDA)
PIR1sensorPin = 5 # PIR 1 sesnor on GPIO pin 5
PIR2sensorPin = 6 # PIR 2 sesnor on GPIO pin 6
GPIO.setup(PIR1sensorPin, GPIO.IN) #Reads the output from PIR 1
GPIO.setup(PIR2sensorPin, GPIO.IN) #Reads the output from PIR 2
pirpins={'5':1,'6':2}
print('Temp = {0:0.2f} *C'.format(BMPSensor.read_temperature()))
print('Pressure = {0:0.2f} Pa'.format(BMPSensor.read_pressure()))
print('Altitude = {0:0.2f} m'.format(BMPSensor.read_altitude()))
print('Sealevel Pressure = {0:0.2f} Pa'.format(BMPSensor.read_sealevel_pressure()))


# MQTT connection set up

def on_connect(client, userdata, flags, rc): #This function is automatically called
    print("Connected with result code "+str(rc))
    client.subscribe("Home_Automation")

def on_publish(client, userdata, mid): #This is called when the method is sent to app
    print("mid: "+str(mid))

def on_subscribe(client, userdata, mid, granted_qos): #Called automatically by MQTT
    print("Subscribed: "+str(mid)+" "+str(granted_qos))

def on_message(client, userdata, msg): #msg is the topic name/ ip address and quality of service
    print(msg.topic+" "+str(msg.qos)+" "+str(msg.payload)) #payload reads from incomming string
    process_message(str(msg.payload)) #Defined when process is sent incomming parameter

# leds pin mapping
ledpins={'red':1,'green':2,'blue':2 ,'white':2}


# dc motor
Forward=21
Backward=20
GPIO.setup(Forward, GPIO.OUT)
GPIO.setup(Backward, GPIO.OUT)
def forward(): 
    GPIO.output(Backward, GPIO.LOW)
    time.sleep(0.1)
    GPIO.output(Forward, GPIO.HIGH)
    print("Moving Forward")

def reverse():
    GPIO.output(Forward, GPIO.LOW)
    time.sleep(0.1)
    GPIO.output(Backward, GPIO.HIGH)
    print("Moving Backward") 
    
def stop():
    GPIO.output(Forward, GPIO.LOW)
    time.sleep(0.1)
    GPIO.output(Backward, GPIO.LOW)
    print("Stop Motor") 

@app.route('/') #When the script is run, first page is the login page.
def index():
    return render_template('login.html')

@app.route('/login',methods=['POST'])
def login():
    username = request.form['username'] #Asks for username and password if user chooses this form of login
    password = request.form['password']
    if username == 'evan' and password == 'evan':
        return render_template('index.html') #If details are correct, the control panel will open, if not user can try fingerprint
    else:
        val = fingerprint_test.verify() #If user selects biometric option, the fingerprint_script willrun, and if fingerprint is correct, opens control panel
        if val == 1:
            return render_template('index.html')
        else:            
            return redirect(url_for('index')) #If fingerprint incorrect, willload page to try again
  
def gen(camera):
    """Video streaming generator function."""
    while True:
        frame = camera.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    """Video streaming route. Put this in the src attribute of an img tag."""
    return Response(gen(Camera()),
                    mimetype='multipart/x-mixed-replace; boundary=frame')



@socketio.on('bmpdata', namespace='/api')
def get_bmp():
    print('Temp = {0:0.2f} *C'.format(BMPSensor.read_temperature()))
    print('Pressure = {0:0.2f} Pa'.format(BMPSensor.read_pressure()))
    print('Altitude = {0:0.2f} m'.format(BMPSensor.read_altitude()))

    (rc, mid) = client.publish("Home_automation_client", "temperature " + str(BMPSensor.read_temperature()), qos=1)
    (rc, mid) = client.publish("Home_automation_client", "pressure " + str(BMPSensor.read_pressure()), qos=1)
    (rc, mid) = client.publish("Home_automation_client", "alltitude " + str(BMPSensor.read_altitude()), qos=1)
    
    socketio.emit('bmpdata',{
        'temperature': format(round(BMPSensor.read_temperature(),2)),
        'pressure': format(round(BMPSensor.read_pressure(),2)),
        'altitude': format(round(BMPSensor.read_altitude(),2)),
    }, namespace='/api')

@socketio.on('leds', namespace='/api')
def turn_leds(led):
    print(led)
    if led == 1:
        GPIO.output(17, GPIO.HIGH)
    else:
        GPIO.output(17, GPIO.LOW)

@socketio.on('motor', namespace='/api')
def turn_motor(data):
    print(data)       
    if data["action"]=='forward':   
        forward()
        time.sleep(0.1)
    elif data["action"]=='reverse':   
        reverse()
        time.sleep(0.1)   
    elif data["action"]=='stop':   
        stop()
        time.sleep(0.1)

def get_rpi(p):
    global pirpins #Global variable
    print(p)
    if GPIO.input(p)==0:  #When output from motion sensor is LOW
        print ("No intruder",pirpins[str(p)])
        (rc, mid) = client.publish("Home_automation_client", "No intruders on pir "+ str(pirpins[str(p)]), qos=1)
        time.sleep(0.1)
    elif GPIO.input(p)==1: #When output from motion sensor is HIGH
        print("An intruder detected",pirpins[str(p)])
        (rc, mid) = client.publish("Home_automation_client", "Intruders on pir " + str(pirpins[str(p)]), qos=1)

        time.sleep(0.1)
 
    socketio.emit('rpidata',{
        'rpi': pirpins[str(p)],
        'state': GPIO.input(p),
    }, namespace='/api')  

# execute the get_rpi function when a HIGH signal is detectedtime counter python
GPIO.add_event_detect(PIR1sensorPin, GPIO.BOTH, callback=lambda x: get_rpi(PIR1sensorPin)) #Event checking on pins, high/low
GPIO.add_event_detect(PIR2sensorPin, GPIO.BOTH, callback=lambda x: get_rpi(PIR2sensorPin)) #Lambda func is called whenever change is detected on pins

def process_message(incomming):
    print("incomming is" + incomming)

    if "on off switch 0" in incomming:          # stop motor
        stop()
        
    if "left" in incomming:          # stop motor
        reverse()
        
    if "right" in incomming:          # stop motor
        forward()
    
    if "lamp 1" in incomming:          # stop motor
        
        turn_leds(1)
    
    if "lamp 0" in incomming:          # stop motor
        #GPIO.output(18, GPIO.LOW)
        turn_leds(0)   
    
@socketio.on('connect', namespace='/api')
def api_connect():
    # need visibility of the global thread object
    global thread
    print('Client connected')

    #Start the random number generator thread only if the thread has not been started before.
    if not thread.isAlive():
        print("Starting Thread")
        #thread = socketio.start_background_task()
    socketio.emit('bmpdata',{
        'temperature': format(round(BMPSensor.read_temperature(),2)),
        'pressure': format(round(BMPSensor.read_pressure(),2)),
        'altitude': format(round(BMPSensor.read_altitude(),2)),
    }, namespace='/api')  

@socketio.on('disconnect', namespace='/api')
def test_disconnect():
    print('Client disconnected')

if __name__ == "__main__":
    client = mqtt.Client()
    #client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect("mqtt.eclipse.org", 1883, 60) #This is the broker URL, import ID. 1883 is broker link and 60 is seconds (refresh)
    client.loop_start() #Starts running MQTT
    socketio.run(app,host = 'localhost', port = 5001)
