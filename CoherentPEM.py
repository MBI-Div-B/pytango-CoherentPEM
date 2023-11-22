#!/usr/bin/env python3
# -*- coding: utf-8 -*-


# Copyright (C) 2023  MBI-Division-B
# MIT License, refer to LICENSE file
# Author: Martin Hennecke / Email: hennecke@mbi-berlin.de

from enum import IntEnum
from tango import AttrWriteType, DevState, DebugIt, DispLevel, Attr, READ_WRITE, CmdArgType, AttributeProxy
from tango.server import Device, attribute, command, device_property
import serial, random, time
import numpy as np

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
    
    ModelName = attribute(label='Model',
                         dtype='DevString',
                         access=AttrWriteType.READ,
                         doc='Model name of the device')
    
    SerialNumber = attribute(label='Serial',
                         dtype='DevString',
                         access=AttrWriteType.READ,
                         doc='Serial number of the device')
    
    Value = attribute(label='Value',
                         dtype='DevDouble',
                         access=AttrWriteType.READ,
                         doc='Queries the last recorded measurement')
    
    Mode = attribute(label='Mode / Unit',
                         dtype='DevEnum',
                         enum_labels=["J", "mJ", "uJ", "W", "mW", "uW"],
                         access=AttrWriteType.READ_WRITE,
                         memorized = True,
                         hw_memorized = True,
                         doc='Sets/queries the sensor measurement mode')
    
    SeqID = attribute(label='Sequence ID',
                         dtype='DevLong',
                         access=AttrWriteType.READ,
                         doc='Queries the sequence ID / time stamp of last recorded measurement')

    Wavelength = attribute(label='Wavelength',
                         dtype='DevDouble',
                         access=AttrWriteType.READ_WRITE,
                         unit='nm',
                         doc='Sets/queries the current wavelength')

    Gain_onoff = attribute(label='Gain Correction',
                         dtype='DevBoolean',
                         access=AttrWriteType.READ_WRITE,
                         doc='Enables/disables gain compensation')

    Gain_factor = attribute(label='Gain Factor',
                         dtype='DevDouble',
                         access=AttrWriteType.READ_WRITE,
                         doc='Sets/queries the gain compensation factor')

    Polling = attribute(label='Polling',
                         dtype='DevLong',
                         unit='ms',
                         access=AttrWriteType.READ_WRITE,
                         doc='Set/queries the polling interval of the power meter')

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
            self.ser.write(bytearray("SYSTem:INFormation:SNUMber?\r",'ascii'))
            self.SN = self.ser.readline().decode("utf-8").lstrip().rstrip().strip('\"')
            self.ser.write(bytearray("SYSTem:INFormation:MODel?\r",'ascii'))
            self.Model = self.ser.readline().decode("utf-8").lstrip().rstrip().strip('\"')
            self.info_stream("Connected to device ID: {:s}".format(self.ID))

            if 'EnergyMax' in self.ID:
                self.ser.write(bytearray("CONFigure:ITEMselect PULS,PER,FLAG,SEQ\r",'ascii'))
                self.ser.write(bytearray("CONFigure:STATistics:ITEMselect MEAN,MIN,MAX,STDV,DOSE,MISS,FLAG,SEQ\r",'ascii'))
                self.ser.write(bytearray("CONFigure:MEASure:STATistics?\r",'ascii'))
                if self.ser.readline().decode("utf-8").lstrip().rstrip() == "ON":
                    self.ser.write(bytearray("CONFigure:STATistics:STARt\r",'ascii'))
                    self.statmode = True
                else:
                    self.statmode = False
            
            if 'PowerMax' in self.ID:
                self.ser.write(bytearray("CONFigure:ITEMselect MEAS,FLAG,TST\r",'ascii'))

            self.value_attr = AttributeProxy(self.get_name()+"/value")
            self.poll_buffer = self.get_attr_poll_ring_depth("Value")

            self.set_status("The device is in ON state")
            self.set_state(DevState.ON)
        except:
            self.error_stream("Could not connect to port {:s}!".format(self.Port))
            self.set_status("The device is in OFF state")
            self.set_state(DevState.OFF)

    def initialize_dynamic_attributes(self):
        if 'EnergyMax' in self.ID:
            Statistics_mode = attribute(name='Statistics_mode',
                            label='Statistics Mode',
                            dtype='DevBoolean',
                            access=AttrWriteType.READ_WRITE,
                            doc='Enables/disables statistics processing mode',
                            fget='read_Statistics_mode',
                            fset='write_Statistics_mode')
            self.add_attribute(Statistics_mode)

            Statistics_min = attribute(name='Statistics_min',
                            label='Min',
                            dtype='DevDouble',
                            access=AttrWriteType.READ,
                            doc='Queries the min value in batch',
                            fget='read_Statistics_min')
            self.add_attribute(Statistics_min)

            Statistics_max = attribute(name='Statistics_max',
                            label='Max',
                            dtype='DevDouble',
                            access=AttrWriteType.READ,
                            doc='Queries the max value in batch',
                            fget='read_Statistics_max')
            self.add_attribute(Statistics_max)

            Statistics_std = attribute(name='Statistics_std',
                            label='Std',
                            dtype='DevDouble',
                            access=AttrWriteType.READ,
                            doc='Queries the standard deviation in batch',
                            fget='read_Statistics_std')
            self.add_attribute(Statistics_std)

            Statistics_dose = attribute(name='Statistics_dose',
                            label='Dose',
                            dtype='DevDouble',
                            access=AttrWriteType.READ,
                            doc='Queries the dose in batch',
                            fget='read_Statistics_dose')
            self.add_attribute(Statistics_dose)

            Statistics_missed = attribute(name='Statistics_missed',
                            label='Missed',
                            dtype='DevLong',
                            access=AttrWriteType.READ,
                            doc='Queries the number of missed pulses in batch',
                            fget='read_Statistics_missed')
            self.add_attribute(Statistics_missed)

            Statistics_bsize = attribute(name='Statistics_bsize',
                            label='Samples',
                            dtype='DevLong',
                            access=AttrWriteType.READ_WRITE,
                            doc='Sets/queries the statistics batch size',
                            fget='read_Statistics_bsize',
                            fset='write_Statistics_bsize')
            self.add_attribute(Statistics_bsize)

            Statistics_rmode = attribute(name='Statistics_rmode',
                            label='Statistics Restart Mode',
                            dtype='DevEnum',
                            enum_labels=["Manual", "Automatic"],
                            access=AttrWriteType.READ_WRITE,
                            doc='Selects the statistics restart behavior at the end of statistical batch',
                            fget='read_Statistics_rmode',
                            fset='write_Statistics_rmode')
            self.add_attribute(Statistics_rmode)

            Decimation_rate = attribute(name='Decimation_rate',
                            label='Decimation Rate',
                            dtype='DevLong',
                            access=AttrWriteType.READ_WRITE,
                            doc='Sets/queries the pulse decimation rate',
                            fget='read_Decimation_rate',
                            fset='write_Decimation_rate')
            self.add_attribute(Decimation_rate)

            Aperture_diameter = attribute(name='Aperture_diameter',
                            label='Aperture Diameter',
                            dtype='DevDouble',
                            access=AttrWriteType.READ_WRITE,
                            unit="mm",
                            doc='Sets/queries the aperture diameter',
                            fget='read_Aperture_diameter',
                            fset='write_Aperture_diameter')
            self.add_attribute(Aperture_diameter)

            Range = attribute(name='Range',
                            label='Range',
                            dtype='DevEnum',
                            enum_labels=["High", "Low"],
                            access=AttrWriteType.READ_WRITE,
                            doc='Selects the meter measurement range',
                            fget='read_Range',
                            fset='write_Range')
            self.add_attribute(Range)

            self.ser.write(bytearray("CONFigure:RANGe:SELect? MAX\r",'ascii'))
            self.maxrange = float(self.ser.readline().decode("utf-8").lstrip().rstrip())

            Trigger_source = attribute(name='Trigger_source',
                            label='Trigger Source',
                            dtype='DevEnum',
                            enum_labels=["Internal", "External"],
                            access=AttrWriteType.READ_WRITE,
                            doc='Selects the trigger source',
                            fget='read_Trigger_source',
                            fset='write_Trigger_source')
            self.add_attribute(Trigger_source)

            Trigger_level = attribute(name='Trigger_level',
                            label='Trigger Level',
                            dtype='DevDouble',
                            access=AttrWriteType.READ_WRITE,
                            unit= '%',
                            doc='Sets/queries the trigger level',
                            fget='read_Trigger_level',
                            fset='write_Trigger_level')
            self.add_attribute(Trigger_level)

            Trigger_slope = attribute(name='Trigger_slope',
                            label='Trigger Slope',
                            dtype='DevEnum',
                            enum_labels=["Positive", "Negative"],
                            access=AttrWriteType.READ_WRITE,
                            doc='Selects the external trigger edge',
                            fget='read_Trigger_slope',
                            fset='write_Trigger_slope')
            self.add_attribute(Trigger_slope)

            Trigger_delay = attribute(name='Trigger_delay',
                            label='Trigger Delay',
                            dtype='DevDouble',
                            access=AttrWriteType.READ_WRITE,
                            unit= 'us',
                            doc='Sets/queries the trigger delay',
                            fget='read_Trigger_delay',
                            fset='write_Trigger_delay')
            self.add_attribute(Trigger_delay)

        if 'PowerMax' in self.ID:
            Sensor_type = attribute(name='Sensor_type',
                            label='Sensor Type',
                            dtype='DevString',
                            access=AttrWriteType.READ,
                            doc='Queries the sensor type',
                            fget='read_Sensor_type')
            self.add_attribute(Sensor_type)

            J_Mode_Trigger_level = attribute(name='J_Mode_Trigger_level',
                            label='Joule Trigger Level',
                            dtype='DevEnum',
                            enum_labels=["LOW", "MEDIUM", "HIGH"],
                            access=AttrWriteType.READ_WRITE,
                            doc='Sets/queries the Joule mode trigger level',
                            fget='read_J_Mode_Trigger_level',
                            fset='write_J_Mode_Trigger_level')
            self.add_attribute(J_Mode_Trigger_level)

            Statistics_mean = attribute(name='Statistics_mean',
                            label='Mean',
                            dtype='DevDouble',
                            access=AttrWriteType.READ,
                            doc='Calculates the rolling average from batch',
                            fget='read_Statistics_calc_mean')
            self.add_attribute(Statistics_mean)

            Statistics_std = attribute(name='Statistics_std',
                            label='Std',
                            dtype='DevDouble',
                            access=AttrWriteType.READ,
                            unit='%',
                            doc='Calculates the standard deviation from batch',
                            fget='read_Statistics_calc_std')
            self.add_attribute(Statistics_std)

            Statistics_min = attribute(name='Statistics_min',
                            label='Min',
                            dtype='DevDouble',
                            access=AttrWriteType.READ,
                            doc='Calculates the min value from batch',
                            fget='read_Statistics_calc_min')
            self.add_attribute(Statistics_min)

            Statistics_max = attribute(name='Statistics_max',
                            label='Max',
                            dtype='DevDouble',
                            access=AttrWriteType.READ,
                            doc='Calculates the max value from batch',
                            fget='read_Statistics_calc_max')
            self.add_attribute(Statistics_max)

            Statistics_bsize = attribute(name='Statistics_bsize',
                            label='Samples',
                            dtype='DevLong',
                            access=AttrWriteType.READ,
                            doc='Queries the statistics batch size from ring buffer',
                            fget='read_Statistics_calc_bsize')
            self.add_attribute(Statistics_bsize)

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
    
    def read_ModelName(self):
        return self.Model
    
    def read_SerialNumber(self):
        return self.SN
    
    def read_Value(self):
        self.ser.write(bytearray("READ?\r",'ascii'))
        response = self.ser.readline().decode("utf-8").lstrip().rstrip()
        data = response.split(',')
        
        if 'EnergyMax' in self.ID:
            if self.statmode == False:
                value = float(data[0])
                self.period = int(data[1])
                self.flags = data[2]
                self.seqid = int(data[3])
                self.min = ''
                self.max = ''
                self.std = ''
                self.dose = ''
                self.missed = ''
            else:
                value = float(data[0])
                self.min = float(data[1])
                self.max = float(data[2])
                self.std = float(data[3])
                self.dose = float(data[4])
                self.missed = int(data[5])
                self.flags = data[6]
                self.seqid = int(data[7])

        if 'PowerMax' in self.ID:
            value = float(data[0])
            self.flags = data[1]
            self.seqid = int(data[2])

        return value * (1000**self.unitscale)

    def read_Mode(self):
        if 'EnergyMax' in self.ID:
            self.ser.write(bytearray("CONFigure:MEASure:TYPE?\r",'ascii'))
        if 'PowerMax' in self.ID:
            self.ser.write(bytearray("CONFigure:MEASure?\r",'ascii'))

        if self.ser.readline().decode("utf-8").lstrip().rstrip() == "J":
            return 0 + self.unitscale
        else:
            return 3 + self.unitscale

    def write_Mode(self, value):
        if value < 3:
            set_mode = "J"
        else:
            set_mode = "W"

        if 'EnergyMax' in self.ID:
           self.ser.write(bytearray("CONFigure:MEASure:TYPE "+set_mode+"\r",'ascii'))
           if self.statmode:
               self.ser.write(bytearray("CONFigure:STATistics:STARt\r",'ascii'))
        if 'PowerMax' in self.ID:
           self.ser.write(bytearray("CONFigure:MEASure "+set_mode+"\r",'ascii'))

        self.unitscale = value%3
        self.unitnames = ['J','mJ','uJ','W','mW','uW']

        value_prop = self.Value.get_properties()
        value_prop.unit = self.unitnames[value]
        self.Value.set_properties(value_prop)

        stat_mean_attr = AttributeProxy(self.get_name()+"/Statistics_mean")
        stat_mean_prop = stat_mean_attr.get_config()
        stat_mean_prop.unit = self.unitnames[value]
        stat_mean_attr.set_config(stat_mean_prop)

        stat_min_attr = AttributeProxy(self.get_name()+"/Statistics_min")
        stat_min_prop = stat_min_attr.get_config()
        stat_min_prop.unit = self.unitnames[value]
        stat_min_attr.set_config(stat_min_prop)

        stat_max_attr = AttributeProxy(self.get_name()+"/Statistics_max")
        stat_max_prop = stat_max_attr.get_config()
        stat_max_prop.unit = self.unitnames[value]
        stat_max_attr.set_config(stat_max_prop)
        
    def read_SeqID(self):
        return self.seqid

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

    def read_Polling(self):
        return self.get_attribute_poll_period("Value")

    def write_Polling(self, value):
        self.poll_attribute("Value", int(value))  

    def read_Statistics_mode(self, attr):
        self.ser.write(bytearray("CONFigure:MEASure:STATistics?\r",'ascii'))
        if self.ser.readline().decode("utf-8").lstrip().rstrip() == "ON":
            attr.set_value(True)
        else:
            attr.set_value(False)
        
    def write_Statistics_mode(self, attr):
        if attr.get_write_value() == True:
            self.ser.write(bytearray("CONFigure:MEASure:STATistics ON\r",'ascii'))
            self.ser.write(bytearray("CONFigure:STATistics:STARt\r",'ascii'))
            self.statmode = True
        else:
            self.ser.write(bytearray("CONFigure:STATistics:STOP\r",'ascii'))
            self.ser.write(bytearray("CONFigure:MEASure:STATistics OFF\r",'ascii'))
            self.statmode = False

    def read_Statistics_min(self, attr):
        attr.set_value(self.min * (1000**self.unitscale))

    def read_Statistics_max(self, attr):
        attr.set_value(self.max * (1000**self.unitscale))

    def read_Statistics_std(self, attr):
        attr.set_value(self.std * (1000**self.unitscale))

    def read_Statistics_dose(self, attr):
        attr.set_value(self.dose * (1000**self.unitscale))

    def read_Statistics_missed(self, attr):
        attr.set_value(self.missed)

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

    def read_Statistics_calc_mean(self, attr):
        value_attr_hist = self.value_attr.history(self.poll_buffer)
        self.value_hist = np.zeros([len(value_attr_hist)])

        for i in range(len(self.value_hist)):
            self.value_hist[i] = value_attr_hist[i].value

        attr.set_value(np.nanmean(self.value_hist))

    def read_Statistics_calc_std(self, attr):
        attr.set_value(100*(np.nanstd(self.value_hist)/np.nanmean(self.value_hist)))
        
    def read_Statistics_calc_min(self, attr):
        attr.set_value(np.nanmin(self.value_hist))

    def read_Statistics_calc_max(self, attr):
        attr.set_value(np.nanmax(self.value_hist))

    def read_Statistics_calc_bsize(self, attr):
        attr.set_value(self.get_attr_poll_ring_depth("Value"))

    def read_Sensor_type(self, attr):
        self.ser.write(bytearray("SYSTem:INFormation:TYPE?\r",'ascii'))
        attr.set_value(self.ser.readline().decode("utf-8").lstrip().rstrip())

    def read_J_Mode_Trigger_level(self, attr):
        self.ser.write(bytearray("TRIGger:PTJ:LEVel?\r",'ascii'))
        response = self.ser.readline().decode("utf-8").lstrip().rstrip()
        if response == "LOW":
            attr.set_value(0)
        else:
            if response == "MEDIUM":
                attr.set_value(1)
            else:
                attr.set_value(2)

    def write_J_Mode_Trigger_level(self, attr):
        if attr.get_write_value() == 0:
            set_trigger_source = "LOW"
        else:
            if attr.get_write_value() == 1:
                set_trigger_source = "MEDIUM"
            else:
                set_trigger_source = "HIGH"

        self.ser.write(bytearray("TRIGger:PTJ:LEVel "+set_trigger_source+"\r",'ascii'))

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
