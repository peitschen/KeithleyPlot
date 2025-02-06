#!/usr/bin/python
import serial
import re

class Keithley():
    def __init__(self, port='COM1', baudrate=19200, bytesize=serial.EIGHTBITS,
                 parity=serial.PARITY_EVEN, stopbits=serial.STOPBITS_ONE, timeout=1,xonxoff=True):
        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.timeout = timeout
        self.xonxoff = xonxoff
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=self.bytesize,
            parity=self.parity,
            stopbits=self.stopbits,
            timeout=self.timeout,
            xonxoff=self.xonxoff 
        )
        
        # check whether we are actually connecting to a 6487
        self.ser.write(b'*IDN?\r\n')
        response = self.ser.readline()
        if u'KEITHLEY INSTRUMENTS INC.,MODEL 6487' not in response.decode('utf-8'):
            raise RuntimeError(u'This does not seem to be a Keithley 6847!')
        
        # compile the regex to parse read out values
        #self.valuepattern = re.compile('^([+|-][0-9]{1}\.[0-9]{2,6}E-[0-9]{2}A).*$')
        self.valuepattern = re.compile(r'^([+|-][0-9]{1}\.[0-9]{2,6}E-[0-9]{2}A).*$')


        # save connected state
        self.connected = True
        self.serialwrite('*RST')
        self.serialwrite('RANG:AUTO ON')
        self.serialwrite('SYST:ZCH ON')
        self.serialwrite('SYST:ZCH OFF')
        self.serialwrite('INIT')

    def read_value(self):
        #"""讀取電流值並解析"""
        if self.connected:
            self.serialwrite('READ?')

            try:
            # 讀取完整的一行數據
                response = self.ser.readline().decode('utf-8', errors='ignore').strip()
            except UnicodeDecodeError:
                print("Warning: Keithley 回應包含無法解碼的字元！")
                return "0"  # 避免 GUI 崩潰
        
            if not response:  # 檢查是否為空
                print("Warning: Keithley 未返回數據")
                return "0"

        # Keithley 6487 返回格式: "+2.843694E-14A,+2.676045E+02,+0.000000E+00"
        # 只提取第一個科學記號數值（忽略 "A"）
            match = re.search(r'([-+]?\d+\.\d+E[-+]?\d+)A', response)

            if match:
                value = match.group(1)  # 提取第一個數據（電流值）
                return value
            else:
                print(f"Warning: 無法解析 Keithley 回應 '{response}'")
                return "0"
    def serialwrite(self, text):
        if self.connected:
            self.ser.write(text.encode() + b'\r\n')

    def zerocorrect(self):
        if self.connected:
            self.serialwrite('*RST') 
            self.serialwrite('*CLS')
            self.serialwrite("FUNC 'CURR'")
            self.serialwrite('SYST:ZCH ON')
            self.serialwrite('RANG 2E-9')
            self.serialwrite('INIT')
            
            self.serialwrite('SYST:ZCOR:STAT OFF')
            self.serialwrite('SYST:ZCOR:ACQ')
            
            self.serialwrite('SYST:ZCOR ON')
            self.serialwrite('CURR:RANG:AUTO ON')
            self.serialwrite('SYST:ZCH OFF')
            self.serialwrite('SYST:ZCH ON')
            self.serialwrite("MED:RANK 5")
            self.serialwrite("MED ON")
            self.serialwrite("AVER:COUN 20")
            self.serialwrite("AVER:TCON MOV")
            self.serialwrite("AVER ON")
            self.read_value()
        
    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
