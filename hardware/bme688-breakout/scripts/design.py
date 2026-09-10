"""Single source of truth for the BME688 breakout: parts, nets and placement.

Both the schematic and the board are generated from the tables below, so the
two can never disagree about a connection.

Interface notes that drive the netlist:
  * BME688 picks its interface from CSB: high = I2C, low/toggling = SPI.
    R5 holds CSB high so an unconnected CS pin means I2C.
  * In I2C mode SDO is the address select pin: GND = 0x76, VDDIO = 0x77.
    JP1 ties it, and is bridged 1-2 (0x76) as manufactured.
  * Q1..Q4 are BSS138 bidirectional level shifters, one per signal, so the
    0.1" header works with 1.8-5.5V logic while the sensor side stays at 3.3V.
"""

BOARD = dict(
    # Board outline, in KiCad page coordinates. 38.1 x 27.94 mm = 1.5" x 1.1".
    x0=100.0, y0=75.0, w=38.1, h=27.94,
    title="BME688 4-in-1 Environmental Sensor Breakout",
    rev="A",
)

TRACE_W = 0.25          # mm, default signal width
POWER_W = 0.4           # mm, used for VIN / +3V3
CLEARANCE = 0.2         # mm
VIA_DIA, VIA_DRILL = 0.6, 0.3

# ref -> (value, lib_id, footprint, x, y, rot, description)
PARTS = {
 'U1': ('BME688', 'BME688_Breakout:BME688', 'Package_LGA:Bosch_LGA-8_3x3mm_P0.8mm_ClockwisePinNumbering',
        111.5, 83.0, 0, 'Bosch 4-in-1 gas/humidity/pressure/temperature sensor, LGA-8'),
 'U2': ('AP2112K-3.3', 'Regulator_Linear:AP2112K-3.3', 'Package_TO_SOT_SMD:SOT-23-5',
        129.0, 95.0, 0, '3.3V 600mA LDO, 2.5-6V input'),
 'Q1': ('BSS138', 'Transistor_FET:BSS138', 'Package_TO_SOT_SMD:SOT-23',
        109.5, 91.0, 0, 'Level shifter, SCK/SCL'),
 'Q2': ('BSS138', 'Transistor_FET:BSS138', 'Package_TO_SOT_SMD:SOT-23',
        114.0, 91.0, 0, 'Level shifter, SDI/SDA'),
 'Q3': ('BSS138', 'Transistor_FET:BSS138', 'Package_TO_SOT_SMD:SOT-23',
        118.5, 91.0, 0, 'Level shifter, SDO/MISO'),
 'Q4': ('BSS138', 'Transistor_FET:BSS138', 'Package_TO_SOT_SMD:SOT-23',
        123.0, 91.0, 0, 'Level shifter, CSB/CS'),
 'R1': ('10k', 'Device:R', 'Resistor_SMD:R_0603_1608Metric',
        115.0, 85.5, 0, 'SCL pull-up, sensor side'),
 'R2': ('10k', 'Device:R', 'Resistor_SMD:R_0603_1608Metric',
        118.5, 85.5, 0, 'SDA pull-up, sensor side'),
 'R3': ('10k', 'Device:R', 'Resistor_SMD:R_0603_1608Metric',
        109.5, 95.0, 0, 'SCK/SCL pull-up, host side'),
 'R4': ('10k', 'Device:R', 'Resistor_SMD:R_0603_1608Metric',
        113.5, 95.0, 0, 'SDI/SDA pull-up, host side'),
 'R5': ('10k', 'Device:R', 'Resistor_SMD:R_0603_1608Metric',
        122.0, 85.5, 0, 'CSB pull-up: selects I2C when CS is left open'),
 'R6': ('10k', 'Device:R', 'Resistor_SMD:R_0603_1608Metric',
        121.5, 95.0, 0, 'CS pull-up, host side'),
 'R7': ('10k', 'Device:R', 'Resistor_SMD:R_0603_1608Metric',
        117.5, 95.0, 0, 'SDO/MISO pull-up, host side'),
 'R8': ('1k',  'Device:R', 'Resistor_SMD:R_0603_1608Metric',
        130.0, 85.0, 0, 'Power LED series resistor'),
 'C1': ('100nF', 'Device:C', 'Capacitor_SMD:C_0603_1608Metric',
        107.8, 81.4, 0, 'VDD decoupling'),
 'C2': ('100nF', 'Device:C', 'Capacitor_SMD:C_0603_1608Metric',
        107.8, 83.9, 0, 'VDDIO decoupling'),
 'C3': ('1uF', 'Device:C', 'Capacitor_SMD:C_0603_1608Metric',
        125.0, 95.0, 0, 'LDO input'),
 'C4': ('1uF', 'Device:C', 'Capacitor_SMD:C_0603_1608Metric',
        130.3, 91.0, 0, 'LDO output'),
 'C5': ('10uF', 'Device:C', 'Capacitor_SMD:C_0603_1608Metric',
        127.0, 91.0, 0, '3.3V bulk'),
 'D1': ('green', 'Device:LED', 'LED_SMD:LED_0603_1608Metric',
        130.0, 82.5, 0, 'Power indicator'),
 'JP1': ('ADDR', 'Jumper:SolderJumper_3_Bridged12',
         'Jumper:SolderJumper-3_P1.3mm_Bridged12_RoundedPad1.0x1.5mm',
         110.0, 87.5, 0, 'I2C address: 1-2 = 0x76 (default), 2-3 = 0x77, open = SPI'),
 'JP2': ('I2C_PU', 'Jumper:SolderJumper_2_Bridged',
         'Jumper:SolderJumper-2_P1.3mm_Bridged_RoundedPad1.0x1.5mm',
         126.0, 85.5, 0, 'Sensor-side I2C pull-ups; cut on daisy-chained boards'),
 'JP3': ('LED_EN', 'Jumper:SolderJumper_2_Bridged',
         'Jumper:SolderJumper-2_P1.3mm_Bridged_RoundedPad1.0x1.5mm',
         130.0, 87.5, 0, 'Cut to disable the power LED'),
 'J1': ('Conn_01x08', 'Connector_Generic:Conn_01x08',
        'Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical',
        110.16, 100.4, 90, 'Host header, 2.54mm'),
 'J2': ('Conn_01x04', 'Connector_Generic:Conn_01x04',
        'Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical',
        115.24, 77.54, 90, '3.3V I2C expansion header, 2.54mm'),
 'J3': ('Qwiic', 'Connector_Generic_MountingPin:Conn_01x04_MountingPin',
        'Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal',
        102.875, 88.97, 270, 'Qwiic / STEMMA QT, JST SH 1.0mm'),
 'J4': ('Qwiic', 'Connector_Generic_MountingPin:Conn_01x04_MountingPin',
        'Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal',
        135.225, 88.97, 90, 'Qwiic / STEMMA QT, JST SH 1.0mm'),
 'TP1': ('SCK', 'Connector:TestPoint', 'TestPoint:TestPoint_Pad_D1.0mm',
         115.5, 81.5, 0, 'Test pad, sensor-side SCK/SCL'),
 'TP2': ('SDI', 'Connector:TestPoint', 'TestPoint:TestPoint_Pad_D1.0mm',
         117.5, 81.5, 0, 'Test pad, sensor-side SDI/SDA'),
 'TP3': ('SDO', 'Connector:TestPoint', 'TestPoint:TestPoint_Pad_D1.0mm',
         119.5, 81.5, 0, 'Test pad, sensor-side SDO'),
 'TP4': ('CSB', 'Connector:TestPoint', 'TestPoint:TestPoint_Pad_D1.0mm',
         121.5, 81.5, 0, 'Test pad, sensor-side CSB'),
 'H1': ('MountingHole', 'Mechanical:MountingHole', 'MountingHole:MountingHole_2.2mm_M2',
        102.5, 77.5, 0, 'M2'),
 'H2': ('MountingHole', 'Mechanical:MountingHole', 'MountingHole:MountingHole_2.2mm_M2',
        135.6, 77.5, 0, 'M2'),
 'H3': ('MountingHole', 'Mechanical:MountingHole', 'MountingHole:MountingHole_2.2mm_M2',
        102.5, 100.44, 0, 'M2'),
 'H4': ('MountingHole', 'Mechanical:MountingHole', 'MountingHole:MountingHole_2.2mm_M2',
        135.6, 100.44, 0, 'M2'),
}

# (ref, pad) -> net.  Pads absent from this table are intentionally unconnected.
CONNECTIONS = [
 # sensor
 ('U1','1','GND'), ('U1','2','CSB'), ('U1','3','SDI'), ('U1','4','SCK'),
 ('U1','5','SDO'), ('U1','6','+3V3'), ('U1','7','GND'), ('U1','8','+3V3'),
 # regulator: EN tied to VIN so it is always enabled
 ('U2','1','VIN'), ('U2','2','GND'), ('U2','3','VIN'), ('U2','5','+3V3'),
 # level shifters: gate on the 3.3V rail, source = sensor side, drain = host side
 ('Q1','1','+3V3'), ('Q1','2','SCK'), ('Q1','3','SCK_H'),
 ('Q2','1','+3V3'), ('Q2','2','SDI'), ('Q2','3','SDI_H'),
 ('Q3','1','+3V3'), ('Q3','2','SDO'), ('Q3','3','SDO_H'),
 ('Q4','1','+3V3'), ('Q4','2','CSB'), ('Q4','3','CS_H'),
 # pull-ups
 ('R1','1','SCK'),   ('R1','2','PU3V3'),
 ('R2','1','SDI'),   ('R2','2','PU3V3'),
 ('R5','1','CSB'),   ('R5','2','+3V3'),
 ('R3','1','SCK_H'), ('R3','2','VIN'),
 ('R4','1','SDI_H'), ('R4','2','VIN'),
 ('R7','1','SDO_H'), ('R7','2','VIN'),
 ('R6','1','CS_H'),  ('R6','2','VIN'),
 # decoupling
 ('C1','1','+3V3'), ('C1','2','GND'),
 ('C2','1','+3V3'), ('C2','2','GND'),
 ('C3','1','VIN'),  ('C3','2','GND'),
 ('C4','1','+3V3'), ('C4','2','GND'),
 ('C5','1','+3V3'), ('C5','2','GND'),
 # power LED
 ('R8','1','+3V3'), ('R8','2','LED_A'),
 ('D1','2','LED_A'), ('D1','1','LED_K'),
 ('JP3','1','LED_K'), ('JP3','2','GND'),
 # address select / pull-up enable
 ('JP1','1','GND'), ('JP1','2','SDO'), ('JP1','3','+3V3'),
 ('JP2','1','+3V3'), ('JP2','2','PU3V3'),
 # host header
 ('J1','1','VIN'), ('J1','2','+3V3'), ('J1','3','GND'), ('J1','4','SCK_H'),
 ('J1','5','SDI_H'), ('J1','6','SDO_H'), ('J1','7','CS_H'), ('J1','8','GND'),
 # 3.3V expansion header
 ('J2','1','+3V3'), ('J2','2','GND'), ('J2','3','SDI'), ('J2','4','SCK'),
 # Qwiic (GND, 3.3V, SDA, SCL) with shells grounded
 ('J3','1','GND'), ('J3','2','+3V3'), ('J3','3','SDI'), ('J3','4','SCK'), ('J3','MP','GND'),
 ('J4','1','GND'), ('J4','2','+3V3'), ('J4','3','SDI'), ('J4','4','SCK'), ('J4','MP','GND'),
 # test pads
 ('TP1','1','SCK'), ('TP2','1','SDI'), ('TP3','1','SDO'), ('TP4','1','CSB'),
]

# Nets that carry power and get the wider trace width.
POWER_NETS = {'VIN', '+3V3', 'PU3V3'}
GND_NET = 'GND'

# Silkscreen pin labels for the two 2.54mm headers.
J1_LABELS = ['VIN', '3V3', 'GND', 'SCK', 'SDI', 'SDO', 'CS', 'GND']
J2_LABELS = ['3V3', 'GND', 'SDA', 'SCL']


def nets():
    """Ordered net name -> list of (ref, pad)."""
    out = {}
    for ref, pad, net in CONNECTIONS:
        out.setdefault(net, []).append((ref, pad))
    return out


def net_numbers():
    """KiCad net index per name; 0 is the reserved unconnected net."""
    return {name: i + 1 for i, name in enumerate(nets())}


# --------------------------------------------------------------------------
# Schematic placement. Independent of the board: laid out to read left to
# right as sensor -> level shifters -> host header, with power along the
# bottom. rot is chosen so supply pins point up and grounds point down.
# --------------------------------------------------------------------------
SCH = {
 'U1':  (100.0,  70.0,   0),
 'C1':  ( 72.0,  60.0,   0),
 'C2':  ( 58.0,  60.0,   0),
 'JP1': (100.0, 135.0,  90),
 'Q1':  (170.0,  85.0,   0),
 'Q2':  (210.0,  85.0,   0),
 'Q3':  (250.0,  85.0,   0),
 'Q4':  (290.0,  85.0,   0),
 'R1':  (150.0,  55.0, 180),
 'R2':  (190.0,  55.0, 180),
 'R5':  (330.0,  55.0, 180),
 'JP2': (150.0,  30.0, 270),
 'R3':  (150.0, 125.0, 180),
 'R4':  (190.0, 125.0, 180),
 'R7':  (230.0, 125.0, 180),
 'R6':  (270.0, 125.0, 180),
 'U2':  ( 80.0, 200.0,   0),
 'C3':  ( 55.0, 212.0,   0),
 'C4':  (110.0, 212.0,   0),
 'C5':  (130.0, 212.0,   0),
 'R8':  (350.0, 175.0,   0),
 'D1':  (350.0, 192.0,  90),
 'JP3': (350.0, 210.0, 270),
 'J1':  (395.0,  95.0,   0),
 'J2':  (395.0, 160.0,   0),
 'J3':  (395.0, 200.0,   0),
 'J4':  (395.0, 235.0,   0),
 'TP1': (200.0, 160.0,   0),
 'TP2': (215.0, 160.0,   0),
 'TP3': (230.0, 160.0,   0),
 'TP4': (245.0, 160.0,   0),
 'H1':  ( 40.0, 265.0,   0),
 'H2':  ( 60.0, 265.0,   0),
 'H3':  ( 80.0, 265.0,   0),
 'H4':  (100.0, 265.0,   0),
}

# Pins joined by a drawn wire instead of a net label, where the connection is
# short and reads better as a wire.
DIRECT_WIRES = [
 (('R8', '2'), ('D1', '2')),
 (('D1', '1'), ('JP3', '1')),
]

# Nets drawn with a power symbol rather than a label.
POWER_SYMBOLS = {
 'GND':  ('power:GND', 'down'),
 '+3V3': ('power:+3V3', 'up'),
 'VIN':  ('BME688_Breakout:VIN', 'up'),
}

# PWR_FLAG markers so ERC sees these nets as driven.
PWR_FLAGS = [('GND', 30.0, 130.0), ('VIN', 50.0, 130.0)]
