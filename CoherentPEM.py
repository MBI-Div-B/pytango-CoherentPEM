#!/usr/bin/env python3
# -*- coding: utf-8 -*-


# Copyright (C) 2023  MBI-Division-B
# MIT License, refer to LICENSE file
# Author: Martin Hennecke / Email: hennecke@mbi-berlin.de

from enum import IntEnum
from tango import AttrWriteType, DevState, DebugIt, DispLevel, Attr, READ_WRITE, CmdArgType
from tango.server import Device, attribute, command, device_property
import serial, random, time

class CoherentPEM(Device):
    '''
    This docstring should describe your Tango Class and optionally
    what it depends on (drivers etc).
    '''

# ------ Device Properties ------ #

    Port = device_property(dtype=str, default_value='/dev/ttyACM0')

# ------ Attributes ------ #

    Device = attribute(label='Device',
                         dtype='DevString',
                         access=AttrWriteType.READ,
                         doc='Device ID string')
    
    Value = attribute(label='Value',
                         dtype='DevString',
                         access=AttrWriteType.READ,
                         doc='Queries the last recorded measurement')

    Mode = attribute(label='Mode',
                         dtype='DevEnum',
                         enum_labels=["Energy", "Power"],
                         access=AttrWriteType.READ_WRITE,
                         doc='Sets/queries the sensor measurement mode')

    Wavelength = attribute(label='Wavelength',
                         dtype='DevDouble',
                         access=AttrWriteType.READ_WRITE,
                         unit= 'nm',
                         doc='Sets/queries the current wavelength')

    Gain_onoff = attribute(label='Gain Correction',
                         dtype='DevBoolean',
                         access=AttrWriteType.READ_WRITE,
                         doc='Enables/disables gain compensation')

    Gain_factor = attribute(label='Gain Factor',
                         dtype='DevDouble',
                         access=AttrWriteType.READ_WRITE,
                         doc='Sets/queries the gain compensation factor')

# ------ default functions that are inherited from parent "Device" ------ #
    def init_device(self):
        Device.init_device(self)
        self.set_state(DevState.INIT)

        try:
            self.info_stream("Connecting on port: {:s}".format(self.Port))
            self.ser = serial.Serial(self.Port, timeout=1, xonxoff=True)
            self.ser.flushInput()
            self.ser.flushOutput()
            self.ser.write(bytearray("*IDN?\r",'ascii'))
            self.ID = self.ser.readline().decode("utf-8").lstrip().rstrip()
            #self.ser.write(bytearray("CONFigure:ITEMselect PULS\r",'ascii'))
            self.info_stream("Connected to device ID: {:s}".format(self.ID))
            self.set_status("The device is in ON state")
            self.set_state(DevState.ON)
            self.ser.write(bytearray("CONFigure:ITEMselect PULS,PER,FLAG,SEQ\r",'ascii'))
            self.ser.write(bytearray("CONFigure:STATistics:ITEMselect MEAN,MIN,MAX,STDV,SEQ\r",'ascii'))
        except:
            self.error_stream("Could not connect to port {:s}!".format(self.Port))
            self.set_status("The device is in OFF state")
            self.set_state(DevState.OFF)

    def initialize_dynamic_attributes(self):
        if 'EnergyMax' in self.ID:
            Statistics_mode = attribute(name='Statistics Mode',
                            dtype='DevBoolean',
                            access=AttrWriteType.READ_WRITE,
                            doc='Enables/disables statistics processing mode',
                            fget='read_Statistics_mode',
                            fset='write_Statistics_mode')
            self.add_attribute(Statistics_mode)

            Statistics_bsize = attribute(name='Statistics Batch Size',
                            dtype='DevLong',
                            access=AttrWriteType.READ_WRITE,
                            doc='Sets/queries the statistics batch size',
                            fget='read_Statistics_bsize',
                            fset='write_Statistics_bsize')
            self.add_attribute(Statistics_bsize)

            Statistics_rmode = attribute(name='Statistics Restart Mode',
                            dtype='DevEnum',
                            enum_labels=["Manual", "Automatic"],
                            access=AttrWriteType.READ_WRITE,
                            doc='Selects the statistics restart behavior at the end of statistical batch',
                            fget='read_Statistics_rmode',
                            fset='write_Statistics_rmode')
            self.add_attribute(Statistics_rmode)

            Decimation_rate = attribute(name='Decimation Rate',
                            dtype='DevLong',
                            access=AttrWriteType.READ_WRITE,
                            doc='Sets/queries the pulse decimation rate',
                            fget='read_Decimation_rate',
                            fset='write_Decimation_rate')
            self.add_attribute(Decimation_rate)

            Aperture_diameter = attribute(name='Aperture Diameter',
                            dtype='DevDouble',
                            access=AttrWriteType.READ_WRITE,
                            unit="mm",
                            doc='Sets/queries the aperture diameter',
                            fget='read_Aperture_diameter',
                            fset='write_Aperture_diameter')
            self.add_attribute(Aperture_diameter)

            Range = attribute(name='Range',
                            dtype='DevEnum',
                            enum_labels=["High", "Low"],
                            access=AttrWriteType.READ_WRITE,
                            doc='Selects the meter measurement range',
                            fget='read_Range',
                            fset='write_Range')
            self.add_attribute(Range)

            self.ser.write(bytearray("CONFigure:RANGe:SELect? MAX\r",'ascii'))
            self.maxrange = float(self.ser.readline().decode("utf-8").lstrip().rstrip())

            Trigger_source = attribute(name='Trigger Source',
                            dtype='DevEnum',
                            enum_labels=["Internal", "External"],
                            access=AttrWriteType.READ_WRITE,
                            doc='Selects the trigger source',
                            fget='read_Trigger_source',
                            fset='write_Trigger_source')
            self.add_attribute(Trigger_source)

            Trigger_level = attribute(name='Trigger Level',
                            dtype='DevDouble',
                            access=AttrWriteType.READ_WRITE,
                            unit= '%',
                            doc='Sets/queries the trigger level',
                            fget='read_Trigger_level',
                            fset='write_Trigger_level')
            self.add_attribute(Trigger_level)

            Trigger_slope = attribute(name='Trigger Slope',
                            dtype='DevEnum',
                            enum_labels=["Positive", "Negative"],
                            access=AttrWriteType.READ_WRITE,
                            doc='Selects the external trigger edge',
                            fget='read_Trigger_slope',
                            fset='write_Trigger_slope')
            self.add_attribute(Trigger_slope)

            Trigger_delay = attribute(name='Trigger Delay',
                            dtype='DevDouble',
                            access=AttrWriteType.READ_WRITE,
                            unit= 'us',
                            doc='Sets/queries the trigger delay',
                            fget='read_Trigger_delay',
                            fset='write_Trigger_delay')
            self.add_attribute(Trigger_delay)

    def delete_device(self):
        self.set_status("The device is in OFF state")
        self.set_state(DevState.OFF)

    def dev_state(self):
        return DevState.ON

    def always_executed_hook(self):
        pass

# ------ Read/Write functions ------ #
    def read_Device(self):
        return self.ID
    
    def read_Value(self):
        #self.ser.write(bytearray("SYSTem:ERRor:COUNt?\r",'ascii'))
        #self.ser.write(bytearray("CONFigure:ITEMselect?\r",'ascii'))
        #self.ser.write(bytearray("TRIGger:BUS:PMODe?\r",'ascii'))
        self.ser.write(bytearray("READ?\r",'ascii'))
        #time.sleep(0.1)
        power = self.ser.readline().decode("utf-8").lstrip().rstrip()

        return power
        # powermW = float(power) * 1000
        # return powermW
        # return str(random.randint(0,9))

    def read_Mode(self):
        if 'EnergyMax' in self.ID:
            self.ser.write(bytearray("CONFigure:MEASure:TYPE?\r",'ascii'))
        if 'PowerMax' in self.ID:
            self.ser.write(bytearray("CONFigure:MEASure?\r",'ascii'))

        change_prop = self.Value.get_properties()
        
        if self.ser.readline().decode("utf-8").lstrip().rstrip() == "J":
            change_prop.unit = "J"
            self.Value.set_properties(change_prop)
            return 0
        else:
            change_prop.unit = "W"
            self.Value.set_properties(change_prop)
            return 1

    def write_Mode(self, value):
        if value == 0:
            set_mode = "J"
        else:
            set_mode = "W"

        if 'EnergyMax' in self.ID:
           self.ser.write(bytearray("CONFigure:MEASure:TYPE "+set_mode+"\r",'ascii'))
        if 'PowerMax' in self.ID:
           self.ser.write(bytearray("CONFigure:MEASure "+set_mode+"\r",'ascii'))

    def read_Wavelength(self):
        self.ser.write(bytearray("CONFigure:WAVElength?\r",'ascii'))
        return float(self.ser.readline().decode("utf-8").lstrip().rstrip())

    def write_Wavelength(self, value):
        self.ser.write(bytearray("CONFigure:WAVElength "+str(value)+"\r",'ascii'))

    def read_Gain_onoff(self):
        self.ser.write(bytearray("CONFigure:GAIN:COMPensation?\r",'ascii'))
        if self.ser.readline().decode("utf-8").lstrip().rstrip() == "ON":
            return True
        else:
            return False

    def write_Gain_onoff(self, value):
        if value == True:
            self.ser.write(bytearray("CONFigure:GAIN:COMPensation ON\r",'ascii'))
        else:
            self.ser.write(bytearray("CONFigure:GAIN:COMPensation OFF\r",'ascii'))

    def read_Gain_factor(self):
        self.ser.write(bytearray("CONFigure:GAIN:FACTor?\r",'ascii'))
        return float(self.ser.readline().decode("utf-8").lstrip().rstrip())

    def write_Gain_factor(self, value):
        self.ser.write(bytearray("CONFigure:GAIN:FACTor "+str(value)+"\r",'ascii'))

    def read_Statistics_mode(self, attr):
        self.ser.write(bytearray("CONFigure:MEASure:STATistics?\r",'ascii'))
        if self.ser.readline().decode("utf-8").lstrip().rstrip() == "ON":
            return True
        else:
            return False
        
    def write_Statistics_mode(self, attr):
        if attr.get_write_value() == True:
            self.ser.write(bytearray("CONFigure:MEASure:STATistics ON\r",'ascii'))
        else:
            self.ser.write(bytearray("CONFigure:MEASure:STATistics OFF\r",'ascii'))

    def read_Statistics_bsize(self, attr):
        self.ser.write(bytearray("CONFigure:STATistics:BSIZe?\r",'ascii'))
        attr.set_value(int(self.ser.readline().decode("utf-8").lstrip().rstrip()))

    def write_Statistics_bsize(self, attr):
        self.ser.write(bytearray("CONFigure:STATistics:BSIZe "+str(attr.get_write_value())+"\r",'ascii'))

    def read_Statistics_rmode(self, attr):
        self.ser.write(bytearray("CONFigure:STATistics:RMOde?\r",'ascii'))
        if self.ser.readline().decode("utf-8").lstrip().rstrip() == "MAN":
           attr.set_value(0)
        else:
           attr.set_value(1)

    def write_Statistics_rmode(self, attr):
        if attr.get_write_value() == 0:
            set_trigger_source = "MAN"
        else:
            set_trigger_source = "AUT"

        self.ser.write(bytearray("CONFigure:STATistics:RMOde "+set_trigger_source+"\r",'ascii'))

    def read_Decimation_rate(self, attr):
        self.ser.write(bytearray("CONFigure:DECimation?\r",'ascii'))
        attr.set_value(int(self.ser.readline().decode("utf-8").lstrip().rstrip()))

    def write_Decimation_rate(self, attr):
        self.ser.write(bytearray("CONFigure:DECimation "+str(attr.get_write_value())+"\r",'ascii'))

    def read_Aperture_diameter(self, attr):
        self.ser.write(bytearray("CONFigure:DIAMeter ?\r",'ascii'))
        attr.set_value(float(self.ser.readline().decode("utf-8").lstrip().rstrip()))

    def write_Aperture_diameter(self, attr):
        self.ser.write(bytearray("CONFigure:DIAMeter "+str(attr.get_write_value())+"\r",'ascii'))

    def read_Range(self, attr):
        self.ser.write(bytearray("CONFigure:RANGe:SELect?\r",'ascii'))
        if float(self.ser.readline().decode("utf-8").lstrip().rstrip()) == self.maxrange:
           attr.set_value(0)
        else:
           attr.set_value(1)

    def write_Range(self, attr):
        if attr.get_write_value() == 0:
            set_range = "MAX"
        else:
            set_range = "MIN"

        self.ser.write(bytearray("CONFigure:RANGe:SELect "+set_range+"\r",'ascii'))

    def read_Trigger_source(self, attr):
        self.ser.write(bytearray("TRIGger:SOURce?\r",'ascii'))
        if self.ser.readline().decode("utf-8").lstrip().rstrip() == "INT":
           attr.set_value(0)
        else:
           attr.set_value(1)

    def write_Trigger_source(self, attr):
        if attr.get_write_value() == 0:
            set_trigger_source = "INT"
        else:
            set_trigger_source = "EXT"

        self.ser.write(bytearray("TRIGger:SOURce "+set_trigger_source+"\r",'ascii'))

    def read_Trigger_level(self, attr):
        self.ser.write(bytearray("TRIGger:LEVel?\r",'ascii'))
        attr.set_value(float(self.ser.readline().decode("utf-8").lstrip().rstrip()))

    def write_Trigger_level(self, attr):
        self.ser.write(bytearray("TRIGger:LEVel "+str(attr.get_write_value())+"\r",'ascii'))

    def read_Trigger_slope(self, attr):
        self.ser.write(bytearray("TRIGger:SLOPe?\r",'ascii'))
        if self.ser.readline().decode("utf-8").lstrip().rstrip() == "POS":
           attr.set_value(0)
        else:
           attr.set_value(1)

    def write_Trigger_slope(self, attr):
        if attr.get_write_value() == 0:
            set_trigger_slope = "POS"
        else:
            set_trigger_slope = "NEG"

        self.ser.write(bytearray("TRIGger:SLOPe "+set_trigger_slope+"\r",'ascii'))

    def read_Trigger_delay(self, attr):
        self.ser.write(bytearray("TRIGger:DELay?\r",'ascii'))
        attr.set_value(float(self.ser.readline().decode("utf-8").lstrip().rstrip()))

    def write_Trigger_delay(self, attr):
        self.ser.write(bytearray("TRIGger:DELay "+str(attr.get_write_value())+"\r",'ascii'))

# ------ COMMANDS ------ #

    @command(dtype_in=str, dtype_out=str, doc_in="enter a query", doc_out="the response")
    def send_query(self, query):
        self.ser.write(bytearray(query+"\r",'ascii'))
        return self.ser.readline().decode("utf-8").lstrip().rstrip() 

    @command(dtype_in=str, dtype_out=str, doc_in="enter a command", doc_out="the response")
    def send_cmd(self, cmd):
        self.ser.write(bytearray(cmd+"\r",'ascii'))
        return ""


# start the server
if __name__ == "__main__":
    CoherentPEM.run_server()
