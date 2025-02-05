#!/usr/bin/python
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox, filedialog

import sys
import glob
import datetime

try:
    import serial
except ImportError:
    print('Please install pyserial!')
    sys.exit()

import threading

try:
    import numpy as np
except ImportError:
    print('Please install numpy!')
    sys.exit()

try:
    import matplotlib
except ImportError:
    print('Please install matplotlib!')
    sys.exit()

matplotlib.use("TKAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from keithley import Keithley


def serial_ports():
    """ Lists serial port names
        :raises EnvironmentError:
            On unsupported or unknown platforms
        :returns:
            A list of the serial ports available on the system
    """
    if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform')

    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result


class KeithleyPlot(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        # we use the grid type of aligning things
        self.grid()

        # initialize a numpy array for the values
        self.i = 0
        self.time = np.zeros((100000, 1))
        self.time[:] = np.nan
        self.values = np.zeros((100000, 1))
        self.values[:] = np.nan

        # empty object for the keithley
        self.keithley = None

        # variable for the connected port
        self.comport = tk.StringVar(master)
        self.portlist = serial_ports()
        self.baudrate = tk.StringVar(master, "19200")  # 預設波特率
        self.bytesize = tk.StringVar(master, "8")      # 預設數據位
        self.parity = tk.StringVar(master, "EVEN")     # 預設校驗位
        self.stopbits = tk.StringVar(master, "1")      # 預設停止位
        self.xonxoff = tk.BooleanVar(master, True)     # 預設 XON/XOFF 開啟
        # check for COM ports
        if len(self.portlist) == 0:
            sys.exit('No COM ports found!')

        self.frequency = tk.StringVar(master)
        self.frequencies = ['0.1 Hz', '0.5 Hz', '1 Hz', '2 Hz', '3 Hz', ]

        # default value for starttime
        self.starttime = None

        self.create_widgets()

    def create_widgets(self):
        # configure the grid - the first line and row should expand
        self.grid_rowconfigure(0, weight=1)
        
        # create a drop down menu for the update frequency
        self.frequencyselector = ttk.OptionMenu(self.master, self.frequency, self.frequencies[2], *self.frequencies)
        self.frequencyselector.grid(row=2, column=1, sticky='W')

        # create a drop down menu for the comport
        self.comportselector = ttk.OptionMenu(self.master, self.comport, self.portlist[0], *self.portlist)
        self.comportselector.grid(row=2, column=0, sticky='W')
        # 波特率選擇
        ttk.Label(self.master, text="Baudrate:").grid(row=3, column=0, sticky='W')
        self.baudrateselector = ttk.OptionMenu(self.master, self.baudrate, "19200","300","600","1200","2400","4800","9600","19200","38400","57600")
        self.baudrateselector.grid(row=3, column=1, sticky='W')

        # 數據位選擇
        ttk.Label(self.master, text="Bytesize:").grid(row=3, column=2, sticky='W')
        self.bytesizeselector = ttk.OptionMenu(self.master, self.bytesize, "8","7", "8")
        self.bytesizeselector.grid(row=3, column=3, sticky='W')

        # 校驗位選擇
        ttk.Label(self.master, text="Parity:").grid(row=3, column=4, sticky='W')
        self.parityselector = ttk.OptionMenu(self.master, self.parity, "EVEN", "NONE", "ODD",)
        self.parityselector.grid(row=3, column=5, sticky='W')

        # 停止位選擇
        ttk.Label(self.master, text="Stopbits:").grid(row=3, column=6, sticky='W')
        self.stopbitsselector = ttk.OptionMenu(self.master, self.stopbits, "1","2")
        self.stopbitsselector.grid(row=3, column=7, sticky='W')

        # XON/XOFF 選擇
        ttk.Label(self.master, text="XON/XOFF:").grid(row=4, column=0, sticky='W')
        self.xonxoffselector = ttk.Checkbutton(self.master, variable=self.xonxoff)
        self.xonxoffselector.grid(row=4, column=1, sticky='W')

        # "Apply Settings" 按鈕
        self.applyb = ttk.Button(self.master, text="Apply Settings", command=self.apply_settings)
        self.applyb.grid(row=4, column=2, sticky='W')

        # clear button
        self.clearb = ttk.Button(self.master, text="Clear", command=self.clearplot)
        self.clearb.grid(row=2, column=2, sticky='W')

        # connect button
        self.connectb = ttk.Button(self.master, text="Connect", command=self.connectkeithley)
        self.connectb.grid(row=2, column=3, sticky='W')

        # zero correct button
        self.zerocorrectb = ttk.Button(self.master, text="Zero Correct", command=self.zerocorrect)
        self.zerocorrectb.grid(row=2, column=4, sticky='W')
        self.zerocorrectb.config(state='disabled')

        # start and stop button
        self.startb = ttk.Button(self.master, text="Start", command=self.start)
        self.startb.grid(row=2, column=5, sticky='W')

        self.stopb = ttk.Button(self.master, text="Stop", command=self.stop)
        self.stopb.grid(row=2, column=6, sticky='W')

        self.startb.config(state='disabled')
        self.stopb.config(state='disabled')

        # button to save the data
        self.saveb = ttk.Button(self.master, text='Save data', command=self.savedata)
        self.saveb.grid(row=2, column=7, sticky='W')

        # label for the current value
        self.valuelabel = ttk.Label(self.master, text='0A', font='bold')
        self.valuelabel.grid(row=1, column=7, sticky='W')

        # make a figure and axes in the figure
        self.f = Figure(figsize=(10, 5), dpi=100)
        self.f.set_facecolor('#f0f0ed')
        self.f.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05)
        self.a = self.f.add_subplot(111)

        # already plot a "line" because we only want to update (not replot every time)
        self.line, = self.a.plot(self.time, self.values, 'r-')

        self.canvas = FigureCanvasTkAgg(self.f, self.master)
        self.canvas.get_tk_widget().grid(row=0, columnspan=8)
        self.canvas.draw()

        # add a toolbar
        self.toolbar_frame = ttk.Frame(self.master)
        toolbar = NavigationToolbar2Tk(self.canvas, self.toolbar_frame)
        toolbar.update()
        self.toolbar_frame.grid(row=1, columnspan=7, sticky='W')

    def clearplot(self):
        # clear the axes of everything
        self.a.clear()
        self.canvas.draw()

        # overwrite variables 
        self.i = 0
        self.time = np.zeros((100000, 1))
        self.time[:] = np.nan
        self.values = np.zeros((100000, 1))
        self.values[:] = np.nan

        # plot the line again, so we have something to update
        self.line, = self.a.plot(self.time, self.values, 'r-')

    def zerocorrect(self):
        self.keithley.zerocorrect()

    def connectkeithley(self):
        # get the selected com port
        comoption = self.comport.get()
        baudrate = int(self.baudrate.get())
        bytesize = int(self.bytesize.get())
        parity = getattr(serial, f"PARITY_{self.parity.get()}")  # 轉換字符串為 serial 參數
        stopbits = float(self.stopbits.get())  # 轉換成 float
        xonxoff = self.xonxoff.get()
        # connect
        try:
            self.keithley = Keithley(
            port=comoption,
            baudrate=baudrate,
            bytesize=bytesize,
            parity=parity,
            stopbits=stopbits,
            xonxoff=xonxoff
            )
            self.connectb.config(text="Disconnect",command=self.toggle_connection)  # 連接成功後變成 "Disconnect"
            self.comportselector.config(state="disabled")  # 禁止修改 COM 端口
            self.baudrateselector.config(state="disabled")
            self.bytesizeselector.config(state="disabled")
            self.parityselector.config(state="disabled")
            self.stopbitsselector.config(state="disabled")
            self.xonxoffselector.config(state="disabled")
            self.applyb.config(state="disabled")
        except RuntimeError as e:
            messagebox.showerror("COM Port error", e)
            self.keithley = None  # 連接失敗時，確保變數為 None
            return

        # adjust the GUI elements
        self.startb.config(state='normal')
        self.stopb.config(state='normal')
        self.zerocorrectb.config(state='normal')


    def printvalue(self):
        # only do this if we are running
        if self.running is True:
            # immediately schedule the next run of this function
            frequency = float(self.frequency.get().replace(' Hz', ''))
            delay = 1 / frequency
            threading.Timer(delay, self.printvalue).start()

            # write the current time and value in the corresponding arrays
            # self.time = np.append(self.time, self.i)
            if self.i == 0:
                self.time[self.i, 0] = 0
            else:
                self.time[self.i, 0] = self.time[self.i - 1, 0] + delay

            # self.values = np.append(self.values, self.keithley.read_value())
            value = self.keithley.read_value()
            #print(value)
            self.valuelabel['text'] = value + 'A'
            self.values[self.i, 0] = float(value)

            # plot - note that we don't use plt.plot, because it is horribly slow
            self.line.set_ydata(self.values[~np.isnan(self.values)])
            self.line.set_xdata(self.time[~np.isnan(self.values)]) 
            
            # rescale axes every hundredth run
            if self.i % 10 == 1:
                self.a.relim()
                self.a.autoscale_view(scalex=False)
                self.a.set_xlim(0, self.time[self.i, 0] + self.time[self.i, 0] / 10 + 10 * delay)

            # draw the new line
            self.canvas.draw_idle()
            self.i = self.i + 1

    def start(self):
        # clear the plot before we start a new measurement
        self.running = True
        self.clearplot()
        self.printvalue()
        self.startb.config(state='disabled')
        self.stopb.config(state='normal')
        self.connectb.config(state="disabled")  # 禁用 Disconnect 按鈕
        self.starttime = datetime.datetime.now()

    def stop(self):
        self.running = False
        self.stopb.config(state='disabled')
        self.startb.config(state='normal')
        self.connectb.config(state='normal')

    def on_closing(self):
        # we should disconnect before we close the program
        self.stop()
        if self.keithley is not None:
            self.keithley.close()
        self.master.destroy()

    def savedata(self):
        # no measurement has been recorded yet
        if self.starttime is None:
            return

        f = filedialog.asksaveasfilename(defaultextension=".txt", initialfile='PicoAmpValues_' + self.starttime.strftime('%Y-%m-%d_%H-%M'))
        print(f)
        if not f:  
            print("User cancelled file save.")
            return

        print(f"Saving data to: {f}")
        comments = u'Starttime: ' + self.starttime.strftime('%Y/%m/%d - %H:%M')
        ydata = self.values[~np.isnan(self.values)]
        xdata = self.time[~np.isnan(self.values)]

        np.savetxt(f, np.dstack((xdata, ydata))[0], fmt=['%1.0d', '%1.14e'], delimiter='\t', header=comments)
    def apply_settings(self):
        """應用新的串口設置"""
        if self.keithley:
            self.keithley.close()  # 先關閉現有連接
            self.keithley = None
            print("Disconnected old Keithley connection.")

        print(f"Applying settings: Baudrate={self.baudrate.get()}, Bytesize={self.bytesize.get()}, Parity={self.parity.get()}, Stopbits={self.stopbits.get()}, XON/XOFF={self.xonxoff.get()}")
    def toggle_connection(self):
        """連接/斷開 Keithley"""
        if  self.keithley:  # 如果已連接，執行斷開
            self.keithley.close()
            self.keithley = None
            self.connectb.config(text="Connect", command=self.connectkeithley)  # 改回 "Connect"
            self.comportselector.config(state="normal")
            self.baudrateselector.config(state="normal")
            self.bytesizeselector.config(state="normal")
            self.parityselector.config(state="normal")
            self.stopbitsselector.config(state="normal")
            self.xonxoffselector.config(state="normal")  # 允許選擇新串口
            self.applyb.config(state="normal")
            self.startb.config(state="disabled")
            print("Disconnected from Keithley.")

root = tk.Tk()
root.geometry("980x640")
app = KeithleyPlot(master=root)
root.protocol("WM_DELETE_WINDOW", app.on_closing)
root.wm_title("Keithley Plot")
app.mainloop()

