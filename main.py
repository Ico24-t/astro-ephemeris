from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import swisseph as swe
from datetime import datetime
import math

app = FastAPI(title="AstroInsight Ephemeris API")

swe.set_ephe_path('/usr/share/ephe')

PLANETS = {
    'sole': swe.SUN, 'luna': swe.MOON, 'mercurio': swe.MERCURY,
    'venere': swe.VENUS, 'marte': swe.MARS, 'giove': swe.JUPITER,
    'saturno': swe.SATURN, 'urano': swe.URANUS, 'nettuno': swe.NEPTUNE,
    'plutone': swe.PLUTO
}

SIGNS = ['Ariete','Toro','Gemelli','Cancro','Leone','Vergine',
         'Bilancia','Scorpione','Sagittario','Capricorno','Acquario','Pesci']

HOUSES = ['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII']

def deg_to_sign(deg):
    deg = deg % 360
    sign_idx = int(deg / 30)
    deg_in_sign = deg % 30
    return SIGNS[sign_idx], round(deg_in_sign, 2)

def calc_julian_day(year, month, day, hour=12, minute=0):
    decimal_hour = hour + minute/60
    return swe.julday(year, month, day, decimal_hour)

class BirthData(BaseModel):
    year: int
    month: int
    day: int
    hour: int = 12
    minute: int = 0
    latitude: float = 41.9028  # Roma default
    longitude: float = 12.4964

class TransitRequest(BaseModel):
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int = 12
    birth_minute: int = 0
    latitude: float = 41.9028
    longitude: float = 12.4964

@app.get("/")
def root():
    return {"service": "AstroInsight Ephemeris", "status": "active"}

@app.post("/natal")
def natal_chart(data: BirthData):
    jd = calc_julian_day(data.year, data.month, data.day, data.hour, data.minute)
    
    planets_data = {}
    for name, planet_id in PLANETS.items():
        pos, _ = swe.calc_ut(jd, planet_id)
        sign, degrees = deg_to_sign(pos[0])
        planets_data[name] = {
            "longitudine": round(pos[0], 4),
            "segno": sign,
            "gradi_nel_segno": degrees,
            "retrogrado": pos[3] < 0
        }
    
    # Case con Placidus
    houses, ascmc = swe.houses(jd, data.latitude, data.longitude, b'P')
    asc_sign, asc_deg = deg_to_sign(ascmc[0])
    mc_sign, mc_deg = deg_to_sign(ascmc[1])
    
    houses_data = {}
    for i, cusp in enumerate(houses):
        sign, deg = deg_to_sign(cusp)
        houses_data[HOUSES[i]] = {"segno": sign, "gradi": round(deg, 2)}
    
    return {
        "pianeti": planets_data,
        "case": houses_data,
        "ascendente": {"segno": asc_sign, "gradi": asc_deg},
        "medio_cielo": {"segno": mc_sign, "gradi": mc_deg},
        "julian_day": jd
    }

@app.post("/transits")
def current_transits(data: TransitRequest):
    now = datetime.utcnow()
    jd_now = calc_julian_day(now.year, now.month, now.day, now.hour, now.minute)
    jd_natal = calc_julian_day(data.birth_year, data.birth_month, data.birth_day, data.birth_hour, data.birth_minute)
    
    natal_planets = {}
    transit_planets = {}
    
    for name, planet_id in PLANETS.items():
        pos_natal, _ = swe.calc_ut(jd_natal, planet_id)
        pos_transit, _ = swe.calc_ut(jd_now, planet_id)
        natal_planets[name] = round(pos_natal[0], 4)
        transit_planets[name] = {
            "longitudine": round(pos_transit[0], 4),
            "segno": deg_to_sign(pos_transit[0])[0],
            "gradi": deg_to_sign(pos_transit[0])[1]
        }
    
    # Calcola aspetti significativi transiti su natale
    aspects = []
    aspect_types = {0: "congiunzione", 60: "sestile", 90: "quadratura", 120: "trigono", 180: "opposizione"}
    
    for t_name, t_data in transit_planets.items():
        for n_name, n_long in natal_planets.items():
            diff = abs(t_data["longitudine"] - n_long) % 360
            if diff > 180:
                diff = 360 - diff
            for angle, aspect_name in aspect_types.items():
                orb = 8 if angle in [0, 90, 180] else 6
                if abs(diff - angle) <= orb:
                    aspects.append({
                        "transito": t_name,
                        "natale": n_name,
                        "aspetto": aspect_name,
                        "orb": round(abs(diff - angle), 2)
                    })
    
    # Ordina per orb più stretto
    aspects.sort(key=lambda x: x["orb"])
    
    return {
        "pianeti_transito": transit_planets,
        "aspetti_significativi": aspects[:10],
        "data_calcolo": now.isoformat()
    }

@app.get("/today")
def today_planets():
    now = datetime.utcnow()
    jd = calc_julian_day(now.year, now.month, now.day, now.hour, now.minute)
    
    planets_data = {}
    for name, planet_id in PLANETS.items():
        pos, _ = swe.calc_ut(jd, planet_id)
        sign, degrees = deg_to_sign(pos[0])
        planets_data[name] = {
            "segno": sign,
            "gradi": degrees,
            "retrogrado": pos[3] < 0
        }
    
    return {
        "data": now.strftime("%d/%m/%Y"),
        "pianeti": planets_data
    }
