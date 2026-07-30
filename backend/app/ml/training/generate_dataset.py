"""
CAT-alyst Enterprise Synthetic Dataset Generator (v2)
======================================================
Realistic, causally-consistent multi-country equipment-rental dataset
for training demand-forecast, anomaly-detection, and predictive-maintenance
models.

Key design points
-----------------
1. All master tables have 100+ rows.
2. Every rental has real booking context: booking engineer name/role,
   business purpose ("Overburden stripping - Pit A", "Post-monsoon road
   grading - km 24-38"), check-in / check-out QR scans.
3. Anomaly signals include the ones Caterpillar highlighted in the PPT:
      * engine_hours_today > 0 AND operator_id is empty  ->  UNAUTHORIZED_USE
      * engine_hours_today == 0 for many days AND operator_id empty
        while the machine is officially checked out       ->  UNACCOUNTED_ASSET
   Plus the standard telemetry-driven signals (excess idle, fuel outlier,
   sensor failure, impossible hours, GPS jump, geofence breach,
   unknown site) and rental-level signals (late return, duplicate
   checkout).
4. Bulk orders are tagged with contract_id/is_bulk_order so the
   anomaly model can exclude them and avoid flagging legitimate
   mining-scale rentals as suspicious.
5. Seasonality is grounded in real regional patterns
   (India monsoon Jun-Sep depresses construction, US/DE snow winter,
   AU dry-season mining, etc). Verified previously against
   demand_summary aggregates.

Outputs -> ml/data/*.csv
"""

from __future__ import annotations
import os, math, random, string
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

HERE = Path(__file__).resolve().parent
# Allow OUT to be overridden via env var so a locked/open CSV doesn't
# block a re-run (Excel often keeps handles on the primary folder).
OUT = Path(os.environ.get("CATALYST_DATA_OUT", str(HERE / "data")))
OUT.mkdir(parents=True, exist_ok=True)

START_DATE = date(2023, 1, 1)
END_DATE   = date(2026, 6, 30)
N_DAYS     = (END_DATE - START_DATE).days + 1

# --- Scale (all master tables >= 100) ---
N_MACHINES      = 550
N_SITES         = 180
N_CUSTOMERS     = 200
N_OPERATORS     = 280
N_SITE_MANAGERS = 100

COUNTRIES = ["India", "USA", "Germany", "Australia"]
COUNTRY_WEIGHTS = [0.35, 0.30, 0.20, 0.15]

# ---------------------------------------------------------------------
# Reference data (cities, models, seasonality, companies, projects)
# ---------------------------------------------------------------------

CITIES = {
    "India": [
        ("Mumbai", 19.0760, 72.8777, False, False),
        ("Delhi", 28.6139, 77.2090, False, False),
        ("Chennai", 13.0827, 80.2707, False, False),
        ("Bengaluru", 12.9716, 77.5946, False, False),
        ("Hyderabad", 17.3850, 78.4867, False, False),
        ("Pune", 18.5204, 73.8567, False, False),
        ("Ahmedabad", 23.0225, 72.5714, False, False),
        ("Jamshedpur", 22.8046, 86.2029, False, True),
        ("Raipur", 21.2514, 81.6296, False, True),
        ("Bhubaneswar", 20.2961, 85.8245, False, True),
        ("Kolkata", 22.5726, 88.3639, False, False),
        ("Nagpur", 21.1458, 79.0882, False, False),
    ],
    "USA": [
        ("Houston", 29.7604, -95.3698, False, False),
        ("Dallas", 32.7767, -96.7970, False, False),
        ("Denver", 39.7392, -104.9903, True, True),
        ("Phoenix", 33.4484, -112.0740, False, True),
        ("Chicago", 41.8781, -87.6298, True, False),
        ("Seattle", 47.6062, -122.3321, True, False),
        ("Minneapolis", 44.9778, -93.2650, True, False),
        ("Anchorage", 61.2181, -149.9003, True, True),
        ("Los Angeles", 34.0522, -118.2437, False, False),
        ("Pittsburgh", 40.4406, -79.9959, True, True),
        ("Atlanta", 33.7490, -84.3880, False, False),
        ("Salt Lake City", 40.7608, -111.8910, True, True),
    ],
    "Germany": [
        ("Berlin", 52.5200, 13.4050, True, False),
        ("Hamburg", 53.5511, 9.9937, True, False),
        ("Munich", 48.1351, 11.5820, True, False),
        ("Cologne", 50.9375, 6.9603, True, False),
        ("Frankfurt", 50.1109, 8.6821, True, False),
        ("Stuttgart", 48.7758, 9.1829, True, False),
        ("Duesseldorf", 51.2277, 6.7735, True, False),
        ("Leipzig", 51.3397, 12.3731, True, True),
        ("Bremen", 53.0793, 8.8017, True, False),
        ("Essen", 51.4556, 7.0116, True, True),
        ("Dortmund", 51.5136, 7.4653, True, True),
        ("Hannover", 52.3759, 9.7320, True, False),
    ],
    "Australia": [
        ("Sydney", -33.8688, 151.2093, False, False),
        ("Melbourne", -37.8136, 144.9631, False, False),
        ("Brisbane", -27.4698, 153.0251, False, False),
        ("Perth", -31.9505, 115.8605, False, True),
        ("Adelaide", -34.9285, 138.6007, False, False),
        ("Newcastle", -32.9283, 151.7817, False, True),
        ("Darwin", -12.4634, 130.8456, False, False),
        ("Karratha", -20.7364, 116.8462, False, True),
        ("Kalgoorlie", -30.7489, 121.4658, False, True),
        ("Port Hedland", -20.3117, 118.6111, False, True),
        ("Gold Coast", -28.0167, 153.4000, False, False),
        ("Mount Isa", -20.7256, 139.4927, False, True),
    ],
}

MANUFACTURERS_MODELS = {
    "Excavator":         [("Caterpillar","320D"),("Caterpillar","336F"),("Caterpillar","349F"),("Caterpillar","390F"),("Komatsu","PC200-8"),("Hitachi","ZX350"),("JCB","JS205")],
    "Bulldozer":         [("Caterpillar","D6T"),("Caterpillar","D8T"),("Caterpillar","D9T"),("Caterpillar","D11T"),("Komatsu","D65PX-18"),("Komatsu","D155A-6")],
    "Wheel Loader":      [("Caterpillar","966M"),("Caterpillar","980M"),("Caterpillar","950GC"),("Komatsu","WA470-8"),("Volvo","L120H")],
    "Backhoe Loader":    [("Caterpillar","420F"),("Caterpillar","428F"),("JCB","3DX Xtra"),("JCB","3CX Compact"),("Case","580N")],
    "Dump Truck":        [("Caterpillar","745C"),("Caterpillar","770G"),("Caterpillar","777G"),("Caterpillar","785C"),("Komatsu","HD465-7"),("Volvo","A40G")],
    "Motor Grader":      [("Caterpillar","12M3"),("Caterpillar","14M3"),("Caterpillar","16M3"),("Komatsu","GD655-6"),("John Deere","672G")],
    "Road Roller":       [("Caterpillar","CS56B"),("Caterpillar","CS78B"),("Bomag","BW 213"),("JCB","VMT 860"),("Hamm","3520")],
    "Concrete Mixer":    [("Schwing Stetter","AM 7 CBM"),("SANY","SY308C-8"),("Putzmeister","TMM 24-4"),("Ajax Fiori","ARGO 4000"),("Liebherr","HTM 1004")],
    "Mobile Crane":      [("Grove","GMK4100L-1"),("Tadano","ATF 60G-3"),("Liebherr","LTM 1050-3.1"),("Terex","AC 100/4L"),("XCMG","QY50KA")],
    "Forklift":          [("Toyota","8FGCU25"),("Hyster","H50FT"),("Caterpillar","EP18NT"),("Crown","SC 6000"),("Linde","H30D")],
    "Skid Steer Loader": [("Caterpillar","236D3"),("Caterpillar","262D3"),("Bobcat","S650"),("Bobcat","S770"),("Kubota","SSV75")],
    "Snow Plow":         [("Western","Wideout XL"),("Fisher","HD2"),("Boss","DXT 9ft2in"),("Caterpillar","VBX18"),("SnowEx","HDV")],
    "Generator":         [("Caterpillar","DE110E0"),("Caterpillar","DE165"),("Cummins","C220D5"),("Kohler","250REOZK"),("Atlas Copco","QAS 60")],
    "Water Pump":        [("Caterpillar","WP450"),("Sykes","CP150"),("Godwin","CD150M"),("Grindex","Major H"),("Tsurumi","HS3.75S")],
    "Air Compressor":    [("Caterpillar","XAS 400"),("Atlas Copco","XAS 185"),("Sullair","185"),("Ingersoll Rand","P185WJD"),("Doosan","P185WDO")],
}
MACHINE_TYPES = list(MANUFACTURERS_MODELS.keys())

SEASONALITY = {
    "Snow Plow": {
        "USA":       [3.0,2.5,1.8,0.3,0.05,0.05,0.05,0.05,0.10,0.50,1.80,3.20],
        "Germany":   [2.7,2.2,1.5,0.4,0.05,0.05,0.05,0.05,0.15,0.50,1.50,2.50],
        "India":     [0.02,0.02,0.02,0.02,0.02,0.02,0.02,0.02,0.02,0.02,0.02,0.02],
        "Australia": [0.02,0.02,0.02,0.05,0.15,0.30,0.40,0.35,0.15,0.05,0.02,0.02],
    },
    "Excavator": {
        "India":     [1.40,1.50,1.60,1.40,1.00,0.50,0.35,0.35,0.55,1.35,1.60,1.55],
        "USA":       [0.70,0.70,1.00,1.30,1.50,1.60,1.55,1.50,1.40,1.30,1.00,0.75],
        "Germany":   [0.55,0.60,0.85,1.30,1.60,1.70,1.65,1.55,1.40,1.20,0.90,0.60],
        "Australia": [1.35,1.40,1.30,1.50,1.55,1.25,1.05,1.05,1.30,1.40,1.40,1.35],
    },
    "Bulldozer": {
        "India":     [1.30,1.45,1.55,1.30,0.95,0.45,0.30,0.30,0.50,1.30,1.55,1.50],
        "USA":       [0.70,0.75,1.00,1.30,1.55,1.65,1.55,1.50,1.40,1.25,1.00,0.75],
        "Germany":   [0.55,0.60,0.85,1.30,1.60,1.70,1.60,1.50,1.40,1.20,0.85,0.60],
        "Australia": [1.30,1.35,1.30,1.45,1.55,1.30,1.15,1.10,1.30,1.40,1.35,1.30],
    },
    "Wheel Loader": {
        "India":     [1.30,1.40,1.50,1.30,1.00,0.55,0.40,0.40,0.60,1.30,1.50,1.50],
        "USA":       [0.75,0.80,1.05,1.30,1.50,1.55,1.50,1.45,1.40,1.30,1.05,0.80],
        "Germany":   [0.60,0.65,0.90,1.30,1.55,1.65,1.60,1.50,1.40,1.20,0.90,0.65],
        "Australia": [1.30,1.35,1.30,1.40,1.50,1.30,1.20,1.15,1.30,1.40,1.35,1.30],
    },
    "Backhoe Loader": {
        "India":     [1.40,1.50,1.55,1.40,1.10,0.60,0.45,0.45,0.70,1.35,1.55,1.50],
        "USA":       [0.75,0.80,1.00,1.25,1.40,1.50,1.45,1.40,1.35,1.25,1.00,0.80],
        "Germany":   [0.60,0.65,0.90,1.25,1.50,1.60,1.55,1.45,1.35,1.20,0.90,0.65],
        "Australia": [1.25,1.30,1.25,1.35,1.45,1.25,1.15,1.10,1.25,1.35,1.30,1.25],
    },
    "Dump Truck": {
        "India":     [1.35,1.40,1.50,1.35,1.00,0.50,0.35,0.35,0.55,1.30,1.50,1.45],
        "USA":       [0.80,0.85,1.00,1.25,1.40,1.50,1.45,1.40,1.35,1.25,1.05,0.85],
        "Germany":   [0.70,0.75,0.95,1.25,1.50,1.60,1.55,1.45,1.35,1.20,0.95,0.75],
        "Australia": [1.35,1.40,1.35,1.45,1.50,1.35,1.25,1.20,1.35,1.40,1.40,1.35],
    },
    "Motor Grader": {
        "India":     [1.50,1.55,1.55,1.35,1.00,0.40,0.25,0.25,0.50,1.40,1.60,1.55],
        "USA":       [0.75,0.80,1.00,1.30,1.50,1.55,1.50,1.45,1.35,1.25,1.00,0.80],
        "Germany":   [0.60,0.65,0.90,1.30,1.55,1.65,1.60,1.50,1.40,1.20,0.90,0.65],
        "Australia": [1.30,1.35,1.30,1.45,1.50,1.30,1.20,1.15,1.30,1.40,1.35,1.30],
    },
    "Road Roller": {
        "India":     [1.60,1.65,1.50,1.25,0.85,0.30,0.20,0.20,0.45,1.50,1.70,1.65],
        "USA":       [0.65,0.70,0.95,1.30,1.55,1.65,1.60,1.50,1.40,1.20,0.90,0.70],
        "Germany":   [0.55,0.60,0.85,1.30,1.60,1.70,1.65,1.55,1.40,1.20,0.85,0.60],
        "Australia": [1.35,1.40,1.30,1.50,1.55,1.25,1.05,1.05,1.30,1.40,1.40,1.35],
    },
    "Concrete Mixer": {
        "India":     [1.40,1.50,1.60,1.40,1.00,0.40,0.25,0.25,0.50,1.35,1.60,1.55],
        "USA":       [0.70,0.75,1.00,1.30,1.50,1.60,1.55,1.50,1.40,1.25,1.00,0.75],
        "Germany":   [0.55,0.60,0.85,1.30,1.60,1.70,1.65,1.55,1.40,1.20,0.90,0.60],
        "Australia": [1.30,1.35,1.30,1.45,1.50,1.25,1.10,1.10,1.30,1.40,1.35,1.30],
    },
    "Mobile Crane": {
        "India":     [1.20,1.30,1.35,1.20,1.00,0.70,0.55,0.55,0.75,1.20,1.35,1.30],
        "USA":       [0.85,0.90,1.05,1.20,1.35,1.40,1.35,1.30,1.25,1.15,1.00,0.90],
        "Germany":   [0.75,0.80,0.95,1.20,1.40,1.45,1.40,1.35,1.25,1.15,0.95,0.80],
        "Australia": [1.20,1.25,1.20,1.30,1.35,1.20,1.10,1.10,1.20,1.25,1.25,1.20],
    },
    "Forklift": {
        "India":     [1.00,1.00,1.05,1.00,0.95,0.90,0.90,0.90,1.00,1.15,1.20,1.10],
        "USA":       [1.00,0.95,1.00,1.00,1.05,1.05,1.05,1.05,1.10,1.15,1.25,1.20],
        "Germany":   [1.00,0.95,1.00,1.00,1.05,1.05,1.05,1.05,1.10,1.15,1.20,1.20],
        "Australia": [1.05,1.00,1.00,1.00,1.05,1.05,1.00,1.00,1.05,1.15,1.20,1.15],
    },
    "Skid Steer Loader": {
        "India":     [1.20,1.30,1.35,1.25,1.00,0.60,0.40,0.40,0.60,1.20,1.35,1.30],
        "USA":       [0.85,0.85,1.05,1.25,1.35,1.40,1.35,1.30,1.25,1.15,1.00,0.85],
        "Germany":   [0.70,0.75,0.95,1.25,1.45,1.50,1.45,1.40,1.30,1.15,0.90,0.70],
        "Australia": [1.20,1.25,1.20,1.30,1.35,1.20,1.10,1.10,1.20,1.25,1.25,1.20],
    },
    "Generator": {
        "India":     [0.90,0.90,1.00,1.00,1.15,1.50,1.70,1.70,1.50,1.15,0.95,0.90],
        "USA":       [1.05,1.00,1.00,1.05,1.10,1.15,1.20,1.35,1.40,1.25,1.10,1.15],
        "Germany":   [1.15,1.05,1.00,1.00,1.00,1.05,1.05,1.05,1.00,1.05,1.10,1.20],
        "Australia": [1.30,1.25,1.15,1.00,0.95,0.95,1.00,1.05,1.00,1.10,1.20,1.30],
    },
    "Water Pump": {
        "India":     [0.80,0.80,0.90,1.00,1.15,1.70,1.90,1.90,1.60,1.10,0.85,0.80],
        "USA":       [0.85,0.85,1.00,1.15,1.25,1.30,1.35,1.40,1.35,1.15,0.95,0.85],
        "Germany":   [0.80,0.80,0.95,1.15,1.30,1.40,1.40,1.35,1.25,1.10,0.90,0.80],
        "Australia": [1.35,1.30,1.15,1.05,1.00,0.95,0.90,0.95,1.05,1.20,1.30,1.40],
    },
    "Air Compressor": {
        "India":     [1.20,1.30,1.35,1.20,0.95,0.55,0.40,0.40,0.60,1.20,1.35,1.30],
        "USA":       [0.85,0.85,1.00,1.25,1.40,1.45,1.40,1.35,1.30,1.20,1.00,0.85],
        "Germany":   [0.70,0.75,0.95,1.25,1.45,1.50,1.45,1.40,1.30,1.15,0.90,0.70],
        "Australia": [1.20,1.25,1.20,1.30,1.35,1.20,1.10,1.10,1.20,1.25,1.25,1.20],
    },
}

BASE_RATE = {
    "Excavator": 850, "Bulldozer": 1200, "Wheel Loader": 700, "Backhoe Loader": 450,
    "Dump Truck": 550, "Motor Grader": 900, "Road Roller": 500, "Concrete Mixer": 400,
    "Mobile Crane": 1500, "Forklift": 200, "Skid Steer Loader": 300,
    "Snow Plow": 350, "Generator": 250, "Water Pump": 150, "Air Compressor": 180,
}
COUNTRY_RATE_MULT = {"India": 0.55, "USA": 1.00, "Germany": 1.10, "Australia": 1.05}
FUEL_CAPACITY = {
    "Excavator": 400, "Bulldozer": 620, "Wheel Loader": 380, "Backhoe Loader": 130,
    "Dump Truck": 750, "Motor Grader": 415, "Road Roller": 200, "Concrete Mixer": 300,
    "Mobile Crane": 500, "Forklift": 55, "Skid Steer Loader": 100,
    "Snow Plow": 90, "Generator": 220, "Water Pump": 60, "Air Compressor": 120,
}
EXPECTED_LIFE_HOURS = {
    "Excavator": 12000, "Bulldozer": 15000, "Wheel Loader": 13000, "Backhoe Loader": 10000,
    "Dump Truck": 18000, "Motor Grader": 14000, "Road Roller": 9000, "Concrete Mixer": 8000,
    "Mobile Crane": 20000, "Forklift": 12000, "Skid Steer Loader": 9000,
    "Snow Plow": 6000, "Generator": 15000, "Water Pump": 8000, "Air Compressor": 10000,
}

# Base company names + division/branch variants gives us 100+ realistic customers.
BASE_COMPANIES = {
    "India":     ["Larsen & Toubro Construction","Tata Projects Ltd","Hindustan Construction Co","GMR Infrastructure","Shapoorji Pallonji Group","Punj Lloyd","Reliance Infrastructure","Coal India Limited","Vedanta Mining","NMDC Limited","Adani Ports & SEZ","IRCON International","Afcons Infrastructure","Gammon India","Dilip Buildcon","Jaiprakash Associates","KEC International","NCC Limited","IL&FS Engineering","Ashoka Buildcon"],
    "USA":       ["Bechtel Corporation","Kiewit Corporation","Fluor Corporation","Turner Construction","Skanska USA","Whiting-Turner","Clark Construction Group","Peter Kiewit Sons","Freeport-McMoRan","Rio Tinto Kennecott","Newmont Mining","Barrick Gold USA","Granite Construction","Balfour Beatty US","AECOM","Jacobs Engineering","Suffolk Construction","Mortenson Construction","Walsh Group","DPR Construction"],
    "Germany":   ["Hochtief AG","Bilfinger SE","STRABAG SE","Wolff & Mueller","Bauer Group","Zueblin AG","Max Boegl Group","Thyssenkrupp Industrial","K+S Kali GmbH","Salzgitter Mannesmann","Wacker Chemie AG","Deutsche Bahn Bau","Porr Deutschland","Implenia Deutschland","Goldbeck GmbH","Ludwig Freytag GmbH","Heitkamp Ingenieur","Diringer & Scheidel","Depenbrock Bau","Kroell Bau"],
    "Australia": ["Leighton Contractors","Downer Group","John Holland Group","Lendlease Australia","BHP Mining Operations","Rio Tinto Australia","Fortescue Metals Group","Newcrest Mining","Multiplex Constructions","CPB Contractors","Laing O'Rourke Australia","Thiess","BMD Constructions","Mirvac Constructions","Georgiou Group","Probuild Constructions","Icon Construction","Watpac Constructions","ADCO Constructions","Fulton Hogan"],
}

BRANCH_SUFFIXES = {
    "India":     ["Chennai Division","Mumbai Metro Division","Delhi NCR Division","Bengaluru Projects","Hyderabad Branch","Eastern Region","Western Region","Kolkata Division","Coal & Minerals Div"],
    "USA":       ["Houston Office","Denver Regional","Chicago Division","West Coast Office","Southeast Region","Rocky Mountain Div","Northwest Division","Mining Services Div","Infrastructure Group"],
    "Germany":   ["Berlin Niederlassung","Hamburg Regional","Munich Sued Div","NRW Division","Rhein-Main Region","Ost Deutschland","Bau Sued","Tiefbau Division","Industrieanlagenbau"],
    "Australia": ["Sydney Regional","Perth Mining Div","Melbourne Division","Queensland Region","Pilbara Operations","Kalgoorlie Branch","Northern Territory Div","Brisbane Projects","Infrastructure Division"],
}

PROJECT_TEMPLATES = {
    "India": {
        "Metro":     ["Chennai Metro Phase 2 - Depot Site","Mumbai Metro Line 3 Underground","Delhi Metro Yellow Line Extension","Bengaluru Namma Metro Phase 3","Hyderabad Metro Airport Corridor","Kolkata Metro East-West Corridor"],
        "Highway":   ["Delhi-Meerut Expressway Package 4","Mumbai-Nagpur Samruddhi Expressway","Bengaluru-Chennai Expressway Phase 1","Ahmedabad-Dholera Expressway","Ganga Expressway Package 2","Bharatmala Corridor NH-27"],
        "Bridge":    ["Zuari Bridge Package B","Bogibeel Rail-cum-Road Extension","Signature Bridge Approach Works","Ganga Setu Foundation Works"],
        "Mining":    ["NMDC Bailadila Iron Ore Mine Expansion","Coal India Talcher Coalfield Deep Extension","Vedanta Rampura Agucha Zinc Mine","Adani Carmichael Coal Handling","Coal India Korba Mine Ext"],
        "Building":  ["Jio World Convention Centre Phase 2","Reliance Corporate Park BKC","Tata Steel Kalinganagar Plant Extension","Infosys Pune Campus Phase 4"],
        "Solar":     ["Adani Kutch Solar Park Phase 3","NTPC Rajasthan Ultra Mega Solar","ReNew Power Rajasthan Site"],
    },
    "USA": {
        "Highway":   ["I-70 Corridor Expansion Denver Segment","I-35 North Extension Austin Segment 4","SR-99 Alaskan Way Tunnel Completion","I-5 Rose Quarter Improvement","I-405 Sepulveda Pass","I-95 Bridge Program"],
        "Bridge":    ["Brent Spence Bridge Replacement","Gerald Desmond Replacement Bridge Rehab","Tappan Zee Bridge Approach"],
        "Airport":   ["LAX Terminal 9 Modernization","JFK Terminal 6 Development","O'Hare 21 Global Terminal","SFO Boarding Area D"],
        "Metro":     ["MBTA Green Line Extension Medford","LA Metro Purple Line Phase 3","BART Silicon Valley Phase II"],
        "Mining":    ["Freeport McMoRan Bagdad Copper Expansion","Rio Tinto Kennecott Bingham Canyon","Newmont Cripple Creek Extension","Barrick Cortez Mine"],
        "Building":  ["Google Kirkland Campus Phase 2","Amazon HQ2 Arlington Site B","Meta Prineville Data Center","Microsoft Redmond Campus Refresh"],
        "Pipeline":  ["Mountain Valley Pipeline Segment 4","Permian Basin Gathering System","Keystone Segment 6 Prep"],
    },
    "Germany": {
        "Metro":     ["Berlin U-Bahn Extension U5","Munich S-Bahn Second Trunk Line","Hamburg U5 Bramfeld Corridor","Frankfurt U-Bahn D-Strecke","Cologne Nord-Sued Stadtbahn"],
        "Highway":   ["A20 Kuestenautobahn Continuation","A100 Berlin Ring Closure Section 17","A44n Neubau Section","A14 Nordverlaengerung"],
        "Bridge":    ["Leverkusener Rheinbruecke Replacement","Rader Hochbruecke Neubau","Salzbachtalbruecke Wiesbaden"],
        "Rail":      ["Stuttgart 21 Feuerbach Tunnel","DB Frankfurt-Mannheim NBS","DB Hannover-Bielefeld NBS"],
        "Mining":    ["K+S Zielitz Potash Mine Development","Salzgitter Iron Ore Extension","Wismut Kupferschiefer Ext"],
        "Building":  ["Siemens Innovation Campus Erlangen","BASF Ludwigshafen Modernization","Bosch Renningen R&D Expansion"],
        "Wind":      ["Cologne Rheinenergie Wind Farm","Nordsee One Offshore Package 3","EnBW Baltic 2 Foundation Refit"],
    },
    "Australia": {
        "Mining":    ["Pilbara Iron Ore Rail Loop - Karratha","BHP Olympic Dam Underground Expansion","Fortescue Solomon Hub Extension","Newcrest Cadia East Panel Cave 2","Rio Tinto Gudai-Darri Iron Ore","BHP South Flank Iron Ore","Fortescue Iron Bridge Magnetite"],
        "Metro":     ["Sydney Metro West Tunnel Segment 4","Melbourne Metro Tunnel Project","Perth METRONET Yanchep Line","Cross River Rail Brisbane"],
        "Highway":   ["Melbourne West Gate Tunnel","Pacific Highway M1 Extension","North East Link Melbourne","Coffs Harbour Bypass"],
        "Bridge":    ["Bridgewater Bridge Replacement Tasmania","New Bridge over Yarra"],
        "Port":      ["Port Botany Container Terminal Expansion","Port of Newcastle Coal Loader Upgrade","Fremantle Outer Harbour Prep"],
        "Building":  ["Barangaroo Central Sydney","Melbourne Quarter Tower","Perth Elizabeth Quay Stage 4"],
    },
}
PROJECT_TYPES = {c: list(PROJECT_TEMPLATES[c].keys()) for c in COUNTRIES}

# Booking-reason templates (business purpose visible in rental record)
BOOKING_REASONS = {
    "Metro":     ["Underground station excavation - Package {n}","Tunnel boring machine backup support","Foundation piling for elevated corridor","Depot yard grading","Muck haulage from tunnel face","Station box shoring works","Ventilation shaft excavation"],
    "Highway":   ["Subgrade preparation - km {kfrom}-{kto}","Bituminous overlay - section {n}","Culvert construction package","Embankment fill compaction","Rock cutting for cutting slopes","Bridge approach earthworks","Shoulder widening works"],
    "Bridge":    ["Pier foundation excavation - P{n}","Cofferdam dewatering","Approach road earthworks","Deck slab casting support","Piling for pier {n}"],
    "Mining":    ["Overburden stripping - Pit {p}","Haul road maintenance - Ramp {r}","Ore hauling from bench {b}","Waste dump construction","Blast hole clearance","Coal seam extraction support","Tailings dam raise"],
    "Building":  ["Basement excavation","Structural steel erection support","Site clearance and grading","Foundation trenching","Materials handling"],
    "Solar":     ["Access road grading","Foundation trenching for module arrays","Cable trench excavation","Site levelling for tracker rows"],
    "Wind":      ["Turbine foundation excavation","Crane pad construction","Access road hardstand"],
    "Rail":      ["Ballast laying support","Overhead equipment installation","Track bed preparation","Formation levelling"],
    "Pipeline":  ["Trenching and pipe laying","Rock breaking for pipeline route","Pipeline coating yard support"],
    "Airport":   ["Runway pavement rehabilitation","Apron expansion earthworks","Taxiway resurfacing","Perimeter road works"],
    "Port":      ["Wharf reconstruction excavation","Container yard grading","Berth deepening dredge support","Rail loop earthworks"],
}
PURPOSE_CATEGORY = {
    "Excavator":"Excavation","Bulldozer":"Earthmoving","Wheel Loader":"Material Handling","Backhoe Loader":"General Utility",
    "Dump Truck":"Hauling","Motor Grader":"Grading","Road Roller":"Compaction","Concrete Mixer":"Concrete Work",
    "Mobile Crane":"Lifting","Forklift":"Material Handling","Skid Steer Loader":"General Utility",
    "Snow Plow":"Snow Clearance","Generator":"Power Supply","Water Pump":"Dewatering","Air Compressor":"Air Supply",
}

HOLIDAYS_BY_COUNTRY = {
    "India":     [(1,14,"Pongal"),(1,26,"Republic Day"),(3,8,"Holi"),(4,14,"Ambedkar Jayanti"),(8,15,"Independence Day"),(10,2,"Gandhi Jayanti"),(10,24,"Dussehra"),(11,12,"Diwali"),(12,25,"Christmas")],
    "USA":       [(1,1,"New Year's Day"),(1,20,"MLK Day"),(2,17,"Presidents Day"),(5,26,"Memorial Day"),(7,4,"Independence Day"),(9,1,"Labor Day"),(11,11,"Veterans Day"),(11,27,"Thanksgiving"),(12,25,"Christmas")],
    "Germany":   [(1,1,"Neujahrstag"),(4,18,"Karfreitag"),(5,1,"Tag der Arbeit"),(5,29,"Christi Himmelfahrt"),(10,3,"Tag der Deutschen Einheit"),(12,25,"1. Weihnachtsfeiertag"),(12,26,"2. Weihnachtsfeiertag")],
    "Australia": [(1,1,"New Year's Day"),(1,26,"Australia Day"),(4,18,"Good Friday"),(4,25,"ANZAC Day"),(6,9,"King's Birthday"),(12,25,"Christmas"),(12,26,"Boxing Day")],
}

FIRST_NAMES = {
    "India":     ["Rajesh","Suresh","Anil","Vikram","Rahul","Amit","Deepak","Manoj","Arjun","Karthik","Naveen","Prakash","Ravi","Sanjay","Ashok","Vinay","Rohan","Aditya","Kunal","Nikhil","Pradeep","Sunil","Ganesh","Balaji","Harish"],
    "USA":       ["James","Michael","Robert","David","John","Chris","Daniel","Matthew","Anthony","Kevin","Brian","Steven","Andrew","Joshua","Ryan","Mark","Paul","Kenneth","Jason","Jeffrey","Timothy","Scott","Eric","Benjamin","Jonathan"],
    "Germany":   ["Klaus","Wolfgang","Hans","Dieter","Juergen","Manfred","Werner","Thomas","Andreas","Michael","Stefan","Frank","Peter","Uwe","Martin","Rainer","Karl","Heinz","Rolf","Gerd","Bernd","Detlef","Ralf","Ulrich","Volker"],
    "Australia": ["Jack","Liam","Noah","William","Oliver","Ethan","Lucas","Mason","Cooper","Xavier","Hunter","Blake","Riley","Tyler","Kai","Callum","Declan","Angus","Jesse","Bailey","Harrison","Archer","Beau","Tobias","Flynn"],
}
LAST_NAMES = {
    "India":     ["Kumar","Sharma","Singh","Patel","Reddy","Nair","Gupta","Iyer","Mehta","Chauhan","Yadav","Verma","Joshi","Malhotra","Chowdhury","Rao","Menon","Pillai","Desai","Bansal","Aggarwal","Bhat","Krishnan","Naidu","Saxena"],
    "USA":       ["Smith","Johnson","Williams","Brown","Jones","Miller","Davis","Wilson","Anderson","Taylor","Thomas","Moore","Martin","Jackson","Lee","Perez","Thompson","White","Harris","Sanchez","Clark","Ramirez","Lewis","Robinson","Walker"],
    "Germany":   ["Mueller","Schmidt","Schneider","Fischer","Weber","Meyer","Wagner","Becker","Schulz","Hoffmann","Koch","Bauer","Richter","Klein","Wolf","Schroeder","Neumann","Schwarz","Zimmermann","Braun","Krueger","Hofmann","Hartmann","Lange","Schmitt"],
    "Australia": ["Smith","Jones","Williams","Brown","Wilson","Taylor","Anderson","Martin","Thompson","Walker","White","Harris","Roberts","Nguyen","Chen","Campbell","King","Robinson","Baker","Hall","Adams","Nelson","Carter","Mitchell","Wright"],
}
ENGINEER_ROLES = ["Site Engineer","Senior Site Engineer","Project Manager","Deputy Project Manager","Procurement Manager","Equipment Manager","Construction Manager","Operations Lead"]

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def pad(n, w=4): return str(n).zfill(w)
def rw_choice(items, weights): return random.choices(items, weights=weights, k=1)[0]

def phone_for(country):
    if country == "India":     return "+91-" + str(random.randint(6000000000, 9999999999))
    if country == "USA":       return "+1-" + str(random.randint(2000000000, 9999999999))
    if country == "Germany":   return "+49-" + str(random.randint(1000000000, 9999999999))
    return "+61-" + str(random.randint(400000000, 499999999))

def gen_name(country):
    return f"{random.choice(FIRST_NAMES[country])} {random.choice(LAST_NAMES[country])}"

def year_growth(d):
    return 1.0 + 0.08 * ((d - START_DATE).days / N_DAYS)

def weekday_factor(d):
    wd = d.weekday()
    if wd == 5: return 0.75
    if wd == 6: return 0.55
    return 1.0

def industry_from_company(name):
    mining_keywords = ["Mining","Coal","NMDC","Vedanta","Freeport","Rio Tinto","Newmont","Barrick","BHP","Fortescue","Newcrest","K+S","Salzgitter","Kennecott","Wismut"]
    infra_keywords  = ["Rail","Metro","IRCON","GMR","Ports","Adani","Deutsche Bahn","DB"]
    if any(k in name for k in mining_keywords): return "Mining"
    if any(k in name for k in infra_keywords):  return "Infrastructure"
    return random.choices(["Construction","Construction","Construction","Infrastructure","Road Works"], weights=[3,3,2,1.5,1])[0]

def fill_reason(project_type, machine_type):
    template = random.choice(BOOKING_REASONS.get(project_type, ["General equipment support"]))
    return (template
            .replace("{n}", str(random.randint(1, 12)))
            .replace("{p}", chr(random.randint(65, 75)))       # Pit A..K
            .replace("{r}", str(random.randint(1, 5)))          # Ramp 1..5
            .replace("{b}", str(random.randint(1, 8)))          # Bench 1..8
            .replace("{kfrom}", str(random.randint(0, 200)))
            .replace("{kto}",   str(random.randint(200, 400))))

# ---------------------------------------------------------------------
# Reference-table builders
# ---------------------------------------------------------------------

def build_holidays():
    rows, hid, hset = [], 0, {c: set() for c in COUNTRIES}
    for c, entries in HOLIDAYS_BY_COUNTRY.items():
        for year in range(START_DATE.year, END_DATE.year + 1):
            for (m, d, name) in entries:
                try: dd = date(year, m, d)
                except ValueError: continue
                if START_DATE <= dd <= END_DATE:
                    hid += 1
                    rows.append({"holiday_id": f"HOL{pad(hid,5)}","country": c,"date": dd.isoformat(),"holiday_name": name,"is_public_holiday": True})
                    hset[c].add(dd)
    return pd.DataFrame(rows), hset


def build_weather():
    rows, wid = [], 0
    for c in COUNTRIES:
        d = START_DATE
        while d <= END_DATE:
            m = d.month
            wid += 1
            if c == "India":
                temp = 22 + 10 * math.sin((m - 4) / 12 * 2 * math.pi)
                rain = 2 + max(0, 30 * math.sin((m - 7) / 12 * 2 * math.pi))
                snow = 0
                storm = int(random.random() < (0.15 if 6 <= m <= 9 else 0.02))
            elif c == "USA":
                temp = 12 + 15 * math.sin((m - 4) / 12 * 2 * math.pi)
                rain = 3 + random.random() * 4
                snow = max(0, (15 - temp) * 0.6) if m in (12, 1, 2, 3) else 0
                storm = int(random.random() < (0.10 if m in (8, 9, 10) else 0.03))
            elif c == "Germany":
                temp = 10 + 13 * math.sin((m - 4) / 12 * 2 * math.pi)
                rain = 3 + random.random() * 3
                snow = max(0, (8 - temp) * 0.4) if m in (12, 1, 2) else 0
                storm = int(random.random() < 0.03)
            else:
                temp = 22 - 10 * math.sin((m - 4) / 12 * 2 * math.pi)
                rain = 4 + max(0, 20 * math.sin((m - 1) / 12 * 2 * math.pi))
                snow = 0
                storm = int(random.random() < (0.08 if m in (11, 12, 1, 2, 3) else 0.02))
            temp = round(temp + np.random.normal(0, 2), 1)
            rows.append({"weather_id": f"W{pad(wid,7)}","date": d.isoformat(),"country": c,"temperature_c": temp,"rainfall_mm": round(max(0, rain + np.random.normal(0, 2)), 1),"snowfall_mm": round(snow, 1),"storm_flag": storm})
            d += timedelta(days=1)
    return pd.DataFrame(rows)


def build_users_ops_mgrs():
    users, ops, mgrs = [], [], []
    uid = 0
    for i in range(N_OPERATORS):
        uid += 1
        country = rw_choice(COUNTRIES, COUNTRY_WEIGHTS)
        first = random.choice(FIRST_NAMES[country]); last = random.choice(LAST_NAMES[country])
        name = f"{first} {last}"
        user_id = f"USR{pad(uid,5)}"
        users.append({"user_id": user_id, "name": name,
                      "email": f"{first.lower()}.{last.lower()}{i+1}@catrental.com",
                      "phone": phone_for(country), "role": "operator", "status": "active",
                      "created_at": (START_DATE - timedelta(days=random.randint(30, 900))).isoformat(),
                      "country": country})
        exp = int(np.clip(np.random.gamma(3.0, 3.0), 1, 30))
        cert = random.choices(["Basic","Advanced","Expert"], weights=[0.4, 0.4, 0.2])[0]
        safety = float(np.clip(np.random.normal(80 + 0.4*exp, 10), 40, 100))
        accidents = int(np.random.poisson(max(0.05, 2.0 - 0.1 * exp)))
        ops.append({"operator_id": f"OP{pad(i+1,4)}","user_id": user_id,
                    "name": name,
                    "license_number": f"LIC-{country[:2].upper()}-{random.randint(100000,999999)}",
                    "experience_years": exp,"certification": cert,
                    "safety_score": round(safety, 1),"accident_history": accidents,
                    "country": country,"status": "active",
                    "emergency_contact": phone_for(country),
                    "created_at": (START_DATE - timedelta(days=random.randint(30, 900))).isoformat()})
    for i in range(N_SITE_MANAGERS):
        uid += 1
        country = rw_choice(COUNTRIES, COUNTRY_WEIGHTS)
        first = random.choice(FIRST_NAMES[country]); last = random.choice(LAST_NAMES[country])
        name = f"{first} {last}"
        user_id = f"USR{pad(uid,5)}"
        users.append({"user_id": user_id, "name": name,
                      "email": f"{first.lower()}.{last.lower()}.mgr{i+1}@catrental.com",
                      "phone": phone_for(country), "role": "site_manager", "status": "active",
                      "created_at": (START_DATE - timedelta(days=random.randint(30, 900))).isoformat(),
                      "country": country})
        mgrs.append({"manager_id": f"MGR{pad(i+1,4)}","user_id": user_id,"name": name,
                     "designation": random.choice(["Site Manager","Project Manager","Operations Lead","Regional Manager"]),
                     "country": country,
                     "created_at": (START_DATE - timedelta(days=random.randint(30, 900))).isoformat()})
    return pd.DataFrame(users), pd.DataFrame(ops), pd.DataFrame(mgrs)


def build_customers():
    rows = []
    seen_names = set()
    i = 0
    while len(rows) < N_CUSTOMERS:
        country = rw_choice(COUNTRIES, COUNTRY_WEIGHTS)
        base = random.choice(BASE_COMPANIES[country])
        # 60% get a branch suffix so we get variety without repeats
        if random.random() < 0.75:
            company = f"{base} - {random.choice(BRANCH_SUFFIXES[country])}"
        else:
            company = base
        if company in seen_names: continue
        seen_names.add(company)
        i += 1
        industry = industry_from_company(company)
        credit = int(np.clip(np.random.normal(700, 80), 500, 850))
        late_lambda = max(0.2, 5.0 - (credit - 500) / 100)
        late_payments = int(np.random.poisson(late_lambda))
        tier = "Enterprise" if credit >= 780 else "Premium" if credit >= 700 else "Standard"
        contact_first = random.choice(FIRST_NAMES[country])
        contact_last  = random.choice(LAST_NAMES[country])
        contact_name  = f"{contact_first} {contact_last}"
        contact_role  = random.choice(ENGINEER_ROLES)
        city_choice   = random.choice(CITIES[country])[0]
        rows.append({"customer_id": f"CUST{pad(i,4)}","company_name": company,"industry": industry,
                     "country": country,"headquarters_city": city_choice,
                     "customer_since": (START_DATE - timedelta(days=random.randint(365, 1800))).isoformat(),
                     "credit_score": credit,"late_payment_count": late_payments,"customer_tier": tier,
                     "primary_contact_name": contact_name,"primary_contact_role": contact_role,
                     "primary_contact_email": f"{contact_first.lower()}.{contact_last.lower()}@{company.split()[0].lower().replace('&','').replace(',','')}.com",
                     "primary_contact_phone": phone_for(country),
                     "payment_terms_days": random.choice([15, 30, 30, 45, 60]),
                     "avg_project_duration_days": random.randint(90, 720)})
    return pd.DataFrame(rows)


def build_sites(managers_df):
    rows = []
    for i in range(N_SITES):
        country = rw_choice(COUNTRIES, COUNTRY_WEIGHTS)
        city, lat, lon, snow_prone, mining_region = random.choice(CITIES[country])
        avail_types = PROJECT_TYPES[country][:]
        if mining_region and "Mining" in avail_types:
            project_type = random.choices(avail_types,
                                          weights=[3 if t == "Mining" else 1 for t in avail_types])[0]
        else:
            project_type = random.choice(avail_types)
        project_name = random.choice(PROJECT_TEMPLATES[country][project_type])
        mgr_pool = managers_df[managers_df["country"] == country]["manager_id"].tolist() or managers_df["manager_id"].tolist()
        mgr = random.choice(mgr_pool)
        lat_j = round(lat + np.random.normal(0, 0.05), 4)
        lon_j = round(lon + np.random.normal(0, 0.05), 4)
        start = START_DATE - timedelta(days=random.randint(30, 720))
        end = start + timedelta(days=random.randint(365, 1500))
        rows.append({"site_id": f"SITE{pad(i+1,4)}","site_name": project_name,"city": city,"country": country,
                     "project_type": project_type,
                     "address": f"{random.randint(1,999)} Industrial Rd, {city}",
                     "latitude": lat_j,"longitude": lon_j,"manager_id": mgr,
                     "risk_level": random.choices(["Low","Medium","High"], weights=[0.4,0.4,0.2])[0],
                     "terrain": random.choice(["Flat","Hilly","Rocky","Coastal","Urban","Desert"]),
                     "is_snow_prone": snow_prone,"is_mining_region": mining_region,
                     "site_start_date": start.isoformat(),"site_expected_end_date": end.isoformat(),
                     "workforce_count": random.randint(20, 800),
                     "machinery_slots": random.randint(5, 40),"status": "active"})
    return pd.DataFrame(rows)


def build_machines(sites_df):
    rows = []
    for i in range(N_MACHINES):
        country = rw_choice(COUNTRIES, COUNTRY_WEIGHTS)
        if country == "India":
            type_w = {"Backhoe Loader":3,"Excavator":3,"Concrete Mixer":2,"Road Roller":2,"Generator":2,"Water Pump":2,"Dump Truck":2,"Mobile Crane":2,"Wheel Loader":2,"Bulldozer":1,"Snow Plow":0.1,"Motor Grader":1,"Forklift":1,"Skid Steer Loader":1,"Air Compressor":1}
        elif country == "USA":
            type_w = {"Excavator":3,"Bulldozer":2,"Dump Truck":2,"Wheel Loader":2,"Snow Plow":2,"Motor Grader":1.5,"Backhoe Loader":1,"Concrete Mixer":1.5,"Road Roller":1.5,"Mobile Crane":2,"Forklift":2,"Skid Steer Loader":2,"Generator":1.5,"Water Pump":1,"Air Compressor":1.5}
        elif country == "Germany":
            type_w = {"Excavator":3,"Bulldozer":2,"Wheel Loader":2,"Dump Truck":2,"Snow Plow":1.5,"Motor Grader":1,"Mobile Crane":2,"Concrete Mixer":1.5,"Road Roller":1.5,"Backhoe Loader":1,"Forklift":2,"Skid Steer Loader":1.5,"Generator":1,"Water Pump":1,"Air Compressor":1.5}
        else:
            type_w = {"Dump Truck":3,"Excavator":3,"Bulldozer":3,"Wheel Loader":2,"Motor Grader":2,"Mobile Crane":2,"Water Pump":1.5,"Generator":2,"Snow Plow":0.2,"Forklift":1.5,"Skid Steer Loader":1,"Backhoe Loader":1,"Road Roller":1.5,"Concrete Mixer":1,"Air Compressor":1.5}
        m_type = random.choices(list(type_w.keys()), weights=list(type_w.values()))[0]
        mfr, model = random.choice(MANUFACTURERS_MODELS[m_type])
        py = random.choices(range(2018, 2026), weights=[1,2,3,3,3,3,3,2])[0]
        years_used = 2025 - py
        base_h = int(np.clip(np.random.normal(1400 * years_used, 400 * max(1, years_used)), 100, 18000))
        candidates = sites_df[sites_df["country"] == country]
        site_row = candidates.sample(1).iloc[0] if len(candidates) else sites_df.sample(1).iloc[0]
        purchase_cost = int(BASE_RATE[m_type] * COUNTRY_RATE_MULT[country] * 220 * random.uniform(0.85, 1.25))
        daily_rate = int(BASE_RATE[m_type] * COUNTRY_RATE_MULT[country] * random.uniform(0.9, 1.2))
        last_service = START_DATE - timedelta(days=random.randint(1, 400))
        next_service = last_service + timedelta(days=random.randint(60, 200))
        mfr_prefix = "".join([c for c in mfr.upper() if c.isalpha()])[:3]
        serial = f"{mfr_prefix}{random.randint(1000000, 9999999)}"
        rows.append({"asset_id": f"MAC{pad(i+1,5)}",
                     "qr_code": f"QR-{pad(i+1,5)}-{''.join(random.choices(string.ascii_uppercase+string.digits, k=6))}",
                     "rfid_tag": f"RFID{random.randint(10000000,99999999)}",
                     "asset_name": f"{mfr} {model} #{i+1:04d}",
                     "equipment_type": m_type,"manufacturer": mfr,"model": model,"serial_number": serial,
                     "purchase_year": py,
                     "engine_type": random.choice(["Diesel","Diesel","Diesel","Electric-Hybrid"]) if m_type != "Snow Plow" else "Attachment-No-Engine",
                     "fuel_type": "Diesel" if m_type not in ("Snow Plow","Forklift") else random.choice(["Diesel","LPG","Electric"]),
                     "fuel_capacity_l": FUEL_CAPACITY[m_type],
                     "horsepower": int(BASE_RATE[m_type] / 3 * random.uniform(0.9, 1.15)),
                     "operating_weight_kg": int(BASE_RATE[m_type] * random.uniform(15, 30)),
                     "country": country,"current_site_id": site_row["site_id"],
                     "current_status": random.choices(["rented","available","maintenance","transit"], weights=[0.55,0.30,0.10,0.05])[0],
                     "total_engine_hours": base_h,"expected_life_hours": EXPECTED_LIFE_HOURS[m_type],
                     "last_service_date": last_service.isoformat(),"next_service_due": next_service.isoformat(),
                     "daily_rental_rate": daily_rate,"purchase_cost": purchase_cost,
                     "condition": random.choices(["Excellent","Good","Fair","Poor"], weights=[0.3,0.4,0.25,0.05])[0],
                     "ownership": random.choices(["Owned","Leased"], weights=[0.7,0.3])[0],
                     "iot_enabled": random.choices([True, False], weights=[0.9, 0.1])[0],
                     "image_url": f"https://images.catrental.com/assets/{m_type.lower().replace(' ','-')}.jpg"})
    return pd.DataFrame(rows)

# ---------------------------------------------------------------------
# Demand engine
# ---------------------------------------------------------------------

def compute_demand(d, country, m_type, weather_row, holiday_set):
    season = SEASONALITY[m_type][country][d.month - 1]
    wd_f = weekday_factor(d)
    rain, snow, storm = weather_row["rainfall_mm"], weather_row["snowfall_mm"], weather_row["storm_flag"]
    if m_type == "Snow Plow":
        weather_mult = 1.0 + min(2.5, snow / 5)
    elif m_type == "Water Pump":
        weather_mult = 1.0 + min(1.5, rain / 15)
    elif m_type == "Generator":
        weather_mult = 1.0 + (0.4 if storm else 0) + min(0.6, rain / 25)
    elif m_type in ("Excavator","Bulldozer","Backhoe Loader","Motor Grader","Road Roller","Concrete Mixer"):
        weather_mult = max(0.4, 1.0 - min(0.5, rain / 40)) if snow == 0 else 0.5
    else:
        weather_mult = 1.0
    hol = 0.4 if d in holiday_set.get(country, set()) else 1.0
    return max(0.0, season * wd_f * weather_mult * hol * year_growth(d) * np.random.normal(1.0, 0.10))

# ---------------------------------------------------------------------
# Rentals + telemetry + maintenance + QR-scan + work-orders
# ---------------------------------------------------------------------

def build_rentals_and_telemetry(machines_df, sites_df, customers_df, operators_df,
                                weather_df, holiday_set):
    weather_lookup = {(r["date"], r["country"]): r for _, r in weather_df.iterrows()}

    rentals, telemetry, maintenance, alerts, qr_scans, work_orders = [], [], [], [], [], []
    demand_agg = {}
    rid = tid = mid = aid = qid = woid = 0

    free_from = {mid_: START_DATE for mid_ in machines_df["asset_id"]}
    eng_hours = dict(zip(machines_df["asset_id"], machines_df["total_engine_hours"]))
    machine_meta = machines_df.set_index("asset_id").to_dict("index")
    site_meta = sites_df.set_index("site_id").to_dict("index")
    sites_by_country = {c: sites_df[sites_df["country"] == c]["site_id"].tolist() for c in COUNTRIES}
    cust_by_country = {c: customers_df[customers_df["country"] == c].to_dict("records") for c in COUNTRIES}
    ops_by_country  = {c: operators_df[operators_df["country"] == c].to_dict("records") for c in COUNTRIES}

    supply = {}
    for _, row in machines_df.iterrows():
        supply.setdefault((row["country"], row["equipment_type"]), []).append(row["asset_id"])

    d = START_DATE
    day_i = 0
    while d <= END_DATE:
        day_i += 1
        for country in COUNTRIES:
            wrow = weather_lookup[(d.isoformat(), country)]
            for m_type in MACHINE_TYPES:
                pool = supply.get((country, m_type), [])
                if not pool: continue
                demand = compute_demand(d, country, m_type, wrow, holiday_set)
                lam = demand * len(pool) * 0.05
                n_new = np.random.poisson(lam)
                available = [m for m in pool if free_from[m] <= d]
                if not available or n_new == 0: continue
                random.shuffle(available)
                for machine_id in available[:min(n_new, len(available))]:
                    rid += 1
                    duration = int(np.clip(np.random.gamma(2.2, 5.0), 2, 90))
                    end_expected = d + timedelta(days=duration)
                    is_bulk = random.random() < 0.20
                    contract_id = f"CTR{random.randint(100000,999999)}" if is_bulk else ""

                    cust = random.choice(cust_by_country[country])
                    if is_bulk and random.random() < 0.6:
                        me = [c for c in cust_by_country[country]
                              if c["industry"] == "Mining" or c["customer_tier"] == "Enterprise"]
                        if me: cust = random.choice(me)

                    site_id = random.choice(sites_by_country[country])
                    site_info = site_meta[site_id]
                    op_pool = ops_by_country[country] or operators_df.to_dict("records")
                    op = random.choice(op_pool)
                    missing_operator = random.random() < 0.012

                    # Booking engineer (from customer side)
                    b_first = random.choice(FIRST_NAMES[country]); b_last = random.choice(LAST_NAMES[country])
                    booking_engineer = f"{b_first} {b_last}"
                    booking_role = random.choice(ENGINEER_ROLES)

                    # Business purpose
                    booking_reason = fill_reason(site_info["project_type"], m_type)

                    credit = cust["credit_score"]
                    late_prob = max(0.02, 0.35 - (credit - 500) / 2000)
                    is_late = random.random() < late_prob
                    late_days = int(np.clip(np.random.gamma(1.5, 2.0), 1, 20)) if is_late else 0
                    actual_return = end_expected + timedelta(days=late_days)
                    free_from[machine_id] = actual_return + timedelta(days=1)

                    daily_rate = machine_meta[machine_id]["daily_rental_rate"]
                    discount = 0.15 if is_bulk else round(random.uniform(0, 0.08), 2)
                    revenue = int(duration * daily_rate * (1 - discount))

                    # ---- QR scans (check-in & check-out) ----
                    qid += 1
                    ci_scan_id = f"SCN{pad(qid,7)}"
                    qr_scans.append({"scan_id": ci_scan_id,"asset_id": machine_id,
                                     "operator_id": "" if missing_operator else op["operator_id"],
                                     "rental_id": f"RENT{pad(rid,6)}",
                                     "timestamp": d.isoformat() + "T08:00:00Z",
                                     "scan_type": "check_in","site_id": site_id,"result": "success"})
                    qid += 1
                    co_scan_id = f"SCN{pad(qid,7)}"
                    qr_scans.append({"scan_id": co_scan_id,"asset_id": machine_id,
                                     "operator_id": "" if missing_operator else op["operator_id"],
                                     "rental_id": f"RENT{pad(rid,6)}",
                                     "timestamp": actual_return.isoformat() + "T17:00:00Z",
                                     "scan_type": "check_out","site_id": site_id,"result": "success"})

                    # Occasional work order for the rental
                    if random.random() < 0.35:
                        woid += 1
                        est_hours = round(duration * random.uniform(4, 9), 1)
                        work_orders.append({"workorder_id": f"WO{pad(woid,6)}","asset_id": machine_id,
                                            "site_id": site_id,
                                            "operator_id": "" if missing_operator else op["operator_id"],
                                            "manager_id": site_info["manager_id"],
                                            "task_description": booking_reason,
                                            "priority": random.choices(["Low","Medium","High","Critical"], weights=[0.3,0.4,0.25,0.05])[0],
                                            "estimated_hours": est_hours,
                                            "status": "Completed",
                                            "created_time": d.isoformat() + "T08:30:00Z",
                                            "completed_time": actual_return.isoformat() + "T17:00:00Z"})

                    # ---- Telemetry days ----
                    machine_life = machine_meta[machine_id]["expected_life_hours"]
                    current_hrs = eng_hours[machine_id]
                    site_lat = site_info["latitude"]; site_lon = site_info["longitude"]
                    prev_operator = op["operator_id"]
                    zero_activity_streak = 0

                    for offset in range(duration):
                        tel_date = d + timedelta(days=offset)
                        if tel_date > END_DATE: break
                        hours_ratio = current_hrs / machine_life

                        base_eh = float(np.clip(np.random.normal(8.5, 1.2), 3, 12))
                        if tel_date.weekday() >= 5: base_eh *= 0.5
                        idle_ratio = float(np.clip(np.random.normal(0.20, 0.08), 0.02, 0.6))

                        # Roll anomalies for this row
                        excess_idle    = random.random() < 0.020
                        fuel_anomaly   = random.random() < 0.010
                        sensor_fail    = random.random() < 0.008
                        gps_jump       = random.random() < 0.004
                        impossible     = random.random() < 0.003
                        unauth_use     = random.random() < 0.008    # engine on, no operator (CAT PPT signal)
                        unacct         = random.random() < 0.005    # engine 0 + no operator + rental active
                        geofence_out   = random.random() < 0.003    # position outside site radius

                        if excess_idle:
                            idle_ratio = float(np.random.uniform(0.75, 0.92))
                        eh_day = base_eh * (1 - idle_ratio)
                        idle_day = base_eh * idle_ratio

                        # Unauthorized use: engine_hours > 0 AND operator empty
                        current_operator = "" if missing_operator else op["operator_id"]
                        if unauth_use and not missing_operator:
                            current_operator = ""      # override for this row
                            eh_day = float(np.random.uniform(3, 9))
                            idle_day = 0.5

                        # Unaccounted asset: engine 0 + operator empty (matches PS "equipment lost/unaccounted")
                        if unacct:
                            current_operator = ""
                            eh_day = 0.0
                            idle_day = 0.0

                        if impossible: eh_day = float(random.uniform(25, 30))

                        current_hrs += eh_day
                        fuel_per_hr = 0.15 * machine_meta[machine_id]["fuel_capacity_l"] * (1 + 0.15 * hours_ratio)
                        expected_fuel = fuel_per_hr * eh_day
                        actual_fuel = expected_fuel * (random.uniform(2.2, 3.5) if fuel_anomaly else np.random.normal(1.0, 0.10))

                        oil_temp     = float(np.random.normal(85 + 10 * hours_ratio, 4))
                        eng_temp     = float(np.random.normal(88 + 8  * hours_ratio, 3))
                        coolant_temp = float(np.random.normal(78 + 6  * hours_ratio, 3))
                        oil_press    = float(np.random.normal(48 - 8  * hours_ratio, 4))
                        batt_v       = float(np.random.normal(24.6 - 0.5 * hours_ratio, 0.4))
                        hyd_press    = float(np.random.normal(210 - 15 * hours_ratio, 12))
                        vibration    = float(np.random.normal(0.3 + 0.4 * hours_ratio, 0.08))
                        rpm          = float(np.random.normal(1800, 120))
                        network      = int(np.random.randint(60, 100))

                        gps_status = "OK"
                        gps_lat = site_lat + np.random.normal(0, 0.002)
                        gps_lon = site_lon + np.random.normal(0, 0.002)
                        if gps_jump:
                            gps_lat += np.random.normal(0, 2.5)
                            gps_lon += np.random.normal(0, 2.5)
                            gps_status = "JUMP"
                        if geofence_out:
                            gps_lat = site_lat + np.random.uniform(0.05, 0.15) * random.choice([-1, 1])
                            gps_lon = site_lon + np.random.uniform(0.05, 0.15) * random.choice([-1, 1])
                            gps_status = "OUT_OF_GEOFENCE"
                        if sensor_fail:
                            gps_status = "OFFLINE"
                            oil_temp = eng_temp = coolant_temp = oil_press = hyd_press = None

                        # Zero-activity streak (for unaccounted asset signal)
                        if eh_day == 0.0 and current_operator == "":
                            zero_activity_streak += 1
                        else:
                            zero_activity_streak = 0

                        tid += 1
                        anomaly_flag, anomaly_type = 0, ""
                        # Priority order in labelling
                        if unauth_use:
                            anomaly_flag = 1; anomaly_type = "unauthorized_use"
                        elif unacct or zero_activity_streak >= 3:
                            anomaly_flag = 1; anomaly_type = "unaccounted_asset"
                        elif excess_idle:
                            anomaly_flag = 1; anomaly_type = "excess_idle"
                        elif fuel_anomaly:
                            anomaly_flag = 1; anomaly_type = "fuel_anomaly"
                        elif sensor_fail:
                            anomaly_flag = 1; anomaly_type = "sensor_failure"
                        elif geofence_out:
                            anomaly_flag = 1; anomaly_type = "geofence_breach"
                        elif gps_jump:
                            anomaly_flag = 1; anomaly_type = "gps_jump"
                        elif impossible:
                            anomaly_flag = 1; anomaly_type = "impossible_hours"
                        elif missing_operator and offset == 0:
                            anomaly_flag = 1; anomaly_type = "missing_operator_at_checkout"

                        telemetry.append({"telemetry_id": tid,
                                          "timestamp": tel_date.isoformat() + "T18:00:00Z",
                                          "date": tel_date.isoformat(),
                                          "asset_id": machine_id,
                                          "operator_id": current_operator,
                                          "previous_operator_id": prev_operator,
                                          "site_id": site_id,
                                          "latitude": round(gps_lat, 5),"longitude": round(gps_lon, 5),
                                          "speed_kmh": round(float(np.clip(np.random.normal(15, 6), 0, 60)), 1),
                                          "engine_hours_today": round(eh_day, 2),
                                          "idle_hours_today": round(idle_day, 2),
                                          "total_engine_hours": round(current_hrs, 1),
                                          "fuel_used_l": round(float(actual_fuel), 2),
                                          "expected_fuel_l": round(float(expected_fuel), 2),
                                          "fuel_level_pct": round(float(np.clip(np.random.normal(55, 20), 5, 100)), 1),
                                          "engine_temperature_c": None if oil_temp is None else round(eng_temp, 1),
                                          "oil_pressure_kpa": None if oil_temp is None else round(oil_press, 1),
                                          "coolant_temperature_c": None if oil_temp is None else round(coolant_temp, 1),
                                          "oil_temperature_c": None if oil_temp is None else round(oil_temp, 1),
                                          "battery_voltage_v": round(batt_v, 2),
                                          "hydraulic_pressure_bar": None if hyd_press is None else round(hyd_press, 1),
                                          "vibration_g": round(vibration, 3),
                                          "rpm": int(rpm),
                                          "gps_status": gps_status,"network_strength_pct": network,
                                          "zero_activity_streak_days": zero_activity_streak,
                                          "is_anomaly": anomaly_flag,"anomaly_type": anomaly_type})
                        if current_operator: prev_operator = current_operator

                        # Correlated maintenance
                        if hours_ratio > 0.85 and oil_temp is not None and oil_temp > 100 and random.random() < 0.05:
                            mid += 1
                            downtime = random.randint(1, 5)
                            issue = random.choice(["Overheating","Hydraulic leak","Oil pressure warning","Coolant loss"])
                            maintenance.append({"maintenance_id": f"MAINT{pad(mid,6)}","asset_id": machine_id,
                                                "date": tel_date.isoformat(),"maintenance_type": "Corrective",
                                                "issue": issue,"description": f"Unplanned service - {issue.lower()} detected via telemetry.",
                                                "performed_by": f"Tech-{random.randint(1,40)}","downtime_days": downtime,
                                                "parts_replaced": random.choice(["Hydraulic hose","Oil filter","Coolant pump","Sensor module"]),
                                                "cost_usd": int(np.random.gamma(2.5, 500)),
                                                "warranty_covered": random.random() < 0.3,"breakdown": True,
                                                "next_service_date": (tel_date + timedelta(days=random.randint(45, 120))).isoformat(),
                                                "status": "Completed"})
                            aid += 1
                            alerts.append({"alert_id": f"ALT{pad(aid,6)}","asset_id": machine_id,
                                           "alert_type": "sensor_threshold","severity": "High",
                                           "message": f"Oil temperature {round(oil_temp,1)}C exceeds safe threshold (95C).",
                                           "generated_time": tel_date.isoformat() + "T18:00:00Z",
                                           "resolved": True,"resolved_by": f"Tech-{random.randint(1,40)}"})

                    eng_hours[machine_id] = current_hrs

                    rentals.append({"rental_id": f"RENT{pad(rid,6)}","asset_id": machine_id,
                                    "customer_id": cust["customer_id"],
                                    "customer_company": cust["company_name"],
                                    "site_id": site_id,
                                    "assigned_operator": "" if missing_operator else op["operator_id"],
                                    "equipment_type": m_type,"country": country,
                                    "check_in_time": d.isoformat() + "T08:00:00Z",
                                    "check_out_time": actual_return.isoformat() + "T17:00:00Z",
                                    "expected_return": end_expected.isoformat() + "T17:00:00Z",
                                    "actual_return": actual_return.isoformat() + "T17:00:00Z",
                                    "rental_days": duration,"late_return_days": late_days,
                                    "daily_rate": daily_rate,"discount": discount,"revenue_usd": revenue,
                                    "rental_status": "completed","is_bulk_order": is_bulk,
                                    "contract_id": contract_id,
                                    "missing_operator_flag": missing_operator,
                                    "booking_engineer_name": booking_engineer,
                                    "booking_engineer_role": booking_role,
                                    "booking_reason": booking_reason,
                                    "purpose_category": PURPOSE_CATEGORY[m_type],
                                    "check_in_scan_id": ci_scan_id,
                                    "check_out_scan_id": co_scan_id,
                                    "weather_severity_at_start": round(float(wrow["rainfall_mm"] + wrow["snowfall_mm"]), 1),
                                    "is_holiday_at_start": d in holiday_set.get(country, set()),
                                    "remarks": "Bulk contract - large project deployment" if is_bulk else "Standard rental"})

                    monday = d - timedelta(days=d.weekday())
                    key = (country, m_type, monday.isoformat())
                    if key not in demand_agg:
                        demand_agg[key] = {"bookings": 0, "revenue": 0}
                    demand_agg[key]["bookings"] += 1
                    demand_agg[key]["revenue"] += revenue

        d += timedelta(days=1)
        if day_i % 200 == 0:
            print(f"  simulated {day_i}/{N_DAYS} days...")

    # Duplicate-checkout anomaly injection at rental level
    # Pick ~0.5% of rentals and clone them with slight time overlap (creates suspicious pattern).
    n_dupes = max(5, int(len(rentals) * 0.005))
    for _ in range(n_dupes):
        r = random.choice(rentals)
        rid += 1
        aid += 1
        rentals.append({**r, "rental_id": f"RENT{pad(rid,6)}",
                        "check_in_time": r["check_in_time"], "check_out_time": r["check_out_time"],
                        "remarks": "SUSPECTED DUPLICATE CHECKOUT — investigate"})
        alerts.append({"alert_id": f"ALT{pad(aid,6)}","asset_id": r["asset_id"],
                       "alert_type": "duplicate_checkout","severity": "Critical",
                       "message": f"Asset {r['asset_id']} has overlapping active rentals.",
                       "generated_time": r["check_in_time"],
                       "resolved": False,"resolved_by": ""})

    # Demand summary
    demand_rows = []
    for (country, m_type, week), agg in demand_agg.items():
        wk_date = date.fromisoformat(week)
        b = agg["bookings"]
        level = "High" if b >= 15 else "Medium" if b >= 6 else "Low"
        demand_rows.append({"country": country,"machine_type": m_type,"week_start": week,
                            "year": wk_date.year,"month": wk_date.month,
                            "iso_week": wk_date.isocalendar().week,
                            "bookings": b,"revenue_usd": agg["revenue"],
                            "seasonality_index": round(SEASONALITY[m_type][country][wk_date.month - 1], 3),
                            "demand_level": level})
    demand_df = pd.DataFrame(demand_rows).sort_values(["country","machine_type","week_start"]).reset_index(drop=True)

    return (pd.DataFrame(rentals), pd.DataFrame(telemetry), pd.DataFrame(maintenance),
            pd.DataFrame(alerts), pd.DataFrame(qr_scans), pd.DataFrame(work_orders), demand_df)


def label_predictive_maintenance(tel_df, maint_df):
    if tel_df.empty: return tel_df
    m = maint_df[["asset_id","date"]].copy()
    m["date"] = pd.to_datetime(m["date"])
    tel = tel_df.copy(); tel["date_dt"] = pd.to_datetime(tel["date"])
    lookup = m.groupby("asset_id")["date"].apply(list).to_dict()
    labels = []
    for _, row in tel.iterrows():
        upcoming = False
        for md in lookup.get(row["asset_id"], []):
            if 0 <= (md - row["date_dt"]).days <= 30:
                upcoming = True; break
        labels.append(int(upcoming))
    tel["maintenance_within_30d"] = labels
    tel.drop(columns=["date_dt"], inplace=True)
    return tel

# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():
    print(f"Generating {START_DATE} -> {END_DATE} ({N_DAYS} days), "
          f"machines={N_MACHINES}, sites={N_SITES}, customers={N_CUSTOMERS}, operators={N_OPERATORS}")
    print("-" * 70)

    print("[1/9] Holidays..."); hol_df, hol_set = build_holidays()
    print("[2/9] Weather..."); weather_df = build_weather()
    print("[3/9] Users / operators / site managers..."); users_df, ops_df, mgrs_df = build_users_ops_mgrs()
    print("[4/9] Customers..."); cust_df = build_customers()
    print("[5/9] Sites..."); sites_df = build_sites(mgrs_df)
    print("[6/9] Machines..."); machines_df = build_machines(sites_df)
    print("[7/9] Rentals + telemetry + maintenance + QR scans + work orders...")
    rentals_df, tel_df, maint_df, alerts_df, qr_df, wo_df, demand_df = \
        build_rentals_and_telemetry(machines_df, sites_df, cust_df, ops_df, weather_df, hol_set)
    print("[8/9] Predictive-maintenance labels..."); tel_df = label_predictive_maintenance(tel_df, maint_df)

    print("[9/9] Writing CSVs to", OUT)
    hol_df.to_csv(OUT / "holiday_calendar.csv", index=False)
    weather_df.to_csv(OUT / "weather_history.csv", index=False)
    users_df.to_csv(OUT / "users.csv", index=False)
    ops_df.to_csv(OUT / "operators.csv", index=False)
    mgrs_df.to_csv(OUT / "site_managers.csv", index=False)
    cust_df.to_csv(OUT / "customers.csv", index=False)
    sites_df.to_csv(OUT / "sites.csv", index=False)
    machines_df.to_csv(OUT / "machines.csv", index=False)
    rentals_df.to_csv(OUT / "rentals.csv", index=False)
    tel_df.to_csv(OUT / "telemetry_daily.csv", index=False)
    maint_df.to_csv(OUT / "maintenance_history.csv", index=False)
    alerts_df.to_csv(OUT / "alerts.csv", index=False)
    qr_df.to_csv(OUT / "qr_scan_log.csv", index=False)
    wo_df.to_csv(OUT / "work_orders.csv", index=False)
    demand_df.to_csv(OUT / "demand_summary.csv", index=False)

    print("-" * 70)
    print("DONE. Row counts:")
    for name, df in [("holiday_calendar",hol_df),("weather_history",weather_df),
                     ("users",users_df),("operators",ops_df),("site_managers",mgrs_df),
                     ("customers",cust_df),("sites",sites_df),("machines",machines_df),
                     ("rentals",rentals_df),("telemetry_daily",tel_df),
                     ("maintenance_history",maint_df),("alerts",alerts_df),
                     ("qr_scan_log",qr_df),("work_orders",wo_df),("demand_summary",demand_df)]:
        print(f"  {name:22s} {len(df):>8}")

    if len(tel_df):
        rate = tel_df["is_anomaly"].mean() * 100
        types = tel_df[tel_df.is_anomaly == 1]["anomaly_type"].value_counts()
        print(f"  telemetry anomaly rate: {rate:.2f}%")
        print("  anomaly type breakdown:")
        for t, n in types.items(): print(f"    {t:35s} {n}")
    if len(rentals_df):
        print(f"  bulk-order share:  {rentals_df['is_bulk_order'].mean()*100:.2f}%")
        print(f"  late-return share: {(rentals_df['late_return_days']>0).mean()*100:.2f}%")


if __name__ == "__main__":
    main()
