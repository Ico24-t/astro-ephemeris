from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import swisseph as swe
from datetime import datetime
import math

app = FastAPI(title="AstroInsight Ephemeris API")

swe.set_ephe_path('/usr/share/ephe')

PLANETS = {
    'sole': swe.SUN,
    'luna': swe.MOON,
    'mercurio': swe.MERCURY,
    'venere': swe.VENUS,
    'marte': swe.MARS,
    'giove': swe.JUPITER,
    'saturno': swe.SATURN,
    'urano': swe.URANUS,
    'nettuno': swe.NEPTUNE,
    'plutone': swe.PLUTO,
    'chirone': swe.CHIRON,
}

SIGNS = ['Ariete','Toro','Gemelli','Cancro','Leone','Vergine',
         'Bilancia','Scorpione','Sagittario','Capricorno','Acquario','Pesci']

HOUSES_LABELS = ['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII']

def deg_to_sign(deg):
    deg = deg % 360
    sign_idx = int(deg / 30)
    deg_in_sign = round(deg % 30, 2)
    return SIGNS[sign_idx], deg_in_sign

def calc_jd(year, month, day, hour=12, minute=0):
    return swe.julday(year, month, day, hour + minute/60)

def planet_data(jd, planet_id):
    pos, _ = swe.calc_ut(jd, planet_id)
    sign, deg = deg_to_sign(pos[0])
    return {
        "longitudine": round(pos[0], 4),
        "segno": sign,
        "gradi": deg,
        "retrogrado": pos[3] < 0
    }

def calc_lilith(jd):
    # Lilith media (nodo lunare apogeo)
    pos, _ = swe.calc_ut(jd, swe.MEAN_APOG)
    sign, deg = deg_to_sign(pos[0])
    return {"segno": sign, "gradi": deg, "longitudine": round(pos[0], 4)}

def calc_nodes(jd):
    # Nodo Nord reale
    pos_n, _ = swe.calc_ut(jd, swe.TRUE_NODE)
    sign_n, deg_n = deg_to_sign(pos_n[0])
    # Nodo Sud = opposto
    pos_s = (pos_n[0] + 180) % 360
    sign_s, deg_s = deg_to_sign(pos_s)
    return {
        "nodo_nord": {"segno": sign_n, "gradi": deg_n, "longitudine": round(pos_n[0], 4)},
        "nodo_sud": {"segno": sign_s, "gradi": deg_s, "longitudine": round(pos_s, 4)}
    }

def calc_fortuna(jd, lat, lon, asc, sun_long, moon_long):
    # Parte della Fortuna = ASC + Luna - Sole
    fortuna = (asc + moon_long - sun_long) % 360
    sign, deg = deg_to_sign(fortuna)
    return {"segno": sign, "gradi": round(deg, 2), "longitudine": round(fortuna, 4)}

def calc_aspects(planets_a, planets_b, orb_major=8, orb_minor=6):
    aspect_types = {
        0: ("congiunzione", orb_major),
        60: ("sestile", orb_minor),
        90: ("quadratura", orb_major),
        120: ("trigono", orb_major),
        150: ("quinconce", 3),
        180: ("opposizione", orb_major)
    }
    aspects = []
    for a_name, a_long in planets_a.items():
        for b_name, b_long in planets_b.items():
            if a_name == b_name:
                continue
            diff = abs(a_long - b_long) % 360
            if diff > 180:
                diff = 360 - diff
            for angle, (asp_name, orb) in aspect_types.items():
                if abs(diff - angle) <= orb:
                    aspects.append({
                        "pianeta_a": a_name,
                        "pianeta_b": b_name,
                        "aspetto": asp_name,
                        "angolo_esatto": angle,
                        "orb": round(abs(diff - angle), 2),
                        "applicante": diff < angle
                    })
    aspects.sort(key=lambda x: x["orb"])
    return aspects

class BirthData(BaseModel):
    year: int
    month: int
    day: int
    hour: int = 12
    minute: int = 0
    latitude: float = 41.9028
    longitude: float = 12.4964

class TransitRequest(BaseModel):
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int = 12
    birth_minute: int = 0
    latitude: float = 41.9028
    longitude: float = 12.4964

class SolarReturnRequest(BaseModel):
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int = 12
    birth_minute: int = 0
    current_year: int
    latitude: float = 41.9028
    longitude: float = 12.4964

class CompatibilityRequest(BaseModel):
    person1_year: int
    person1_month: int
    person1_day: int
    person1_hour: int = 12
    person1_minute: int = 0
    person1_lat: float = 41.9028
    person1_lon: float = 12.4964
    person2_year: int
    person2_month: int
    person2_day: int
    person2_hour: int = 12
    person2_minute: int = 0
    person2_lat: float = 41.9028
    person2_lon: float = 12.4964

@app.get("/")
def root():
    return {"service": "AstroInsight Ephemeris", "status": "active", "version": "2.0"}

@app.get("/today")
def today_planets():
    now = datetime.utcnow()
    jd = calc_jd(now.year, now.month, now.day, now.hour, now.minute)
    planets_data = {}
    for name, pid in PLANETS.items():
        planets_data[name] = planet_data(jd, pid)
    nodes = calc_nodes(jd)
    lilith = calc_lilith(jd)
    return {
        "data": now.strftime("%d/%m/%Y"),
        "ora_utc": now.strftime("%H:%M"),
        "pianeti": planets_data,
        "nodi_lunari": nodes,
        "lilith": lilith
    }

@app.post("/natal")
def natal_chart(data: BirthData):
    jd = calc_jd(data.year, data.month, data.day, data.hour, data.minute)

    # Pianeti
    planets_data = {}
    for name, pid in PLANETS.items():
        planets_data[name] = planet_data(jd, pid)

    # Nodi e Lilith
    nodes = calc_nodes(jd)
    lilith = calc_lilith(jd)

    # Case con Placidus
    houses, ascmc = swe.houses(jd, data.latitude, data.longitude, b'P')
    asc_long = ascmc[0]
    mc_long = ascmc[1]
    asc_sign, asc_deg = deg_to_sign(asc_long)
    mc_sign, mc_deg = deg_to_sign(mc_long)

    houses_data = {}
    for i, cusp in enumerate(houses):
        sign, deg = deg_to_sign(cusp)
        houses_data[HOUSES_LABELS[i]] = {"segno": sign, "gradi": round(deg, 2), "longitudine": round(cusp, 4)}

    # Parte della Fortuna
    fortuna = calc_fortuna(jd, data.latitude, data.longitude,
                           asc_long, planets_data['sole']['longitudine'],
                           planets_data['luna']['longitudine'])

    # Aspetti natali
    long_map = {name: pd['longitudine'] for name, pd in planets_data.items()}
    aspects = calc_aspects(long_map, long_map)

    return {
        "pianeti": planets_data,
        "case": houses_data,
        "ascendente": {"segno": asc_sign, "gradi": asc_deg, "longitudine": round(asc_long, 4)},
        "medio_cielo": {"segno": mc_sign, "gradi": mc_deg, "longitudine": round(mc_long, 4)},
        "nodi_lunari": nodes,
        "lilith": lilith,
        "parte_fortuna": fortuna,
        "aspetti_natali": aspects[:20],
        "julian_day": jd
    }

@app.post("/transits")
def current_transits(data: TransitRequest):
    now = datetime.utcnow()
    jd_now = calc_jd(now.year, now.month, now.day, now.hour, now.minute)
    jd_natal = calc_jd(data.birth_year, data.birth_month, data.birth_day,
                       data.birth_hour, data.birth_minute)

    natal_longs = {}
    transit_planets = {}

    for name, pid in PLANETS.items():
        pos_n, _ = swe.calc_ut(jd_natal, pid)
        natal_longs[name] = pos_n[0]
        transit_planets[name] = planet_data(jd_now, pid)

    nodes_natal = calc_nodes(jd_natal)
    natal_longs['nodo_nord'] = nodes_natal['nodo_nord']['longitudine']

    transit_longs = {name: pd['longitudine'] for name, pd in transit_planets.items()}
    aspects = calc_aspects(transit_longs, natal_longs)

    nodes_now = calc_nodes(jd_now)
    lilith_now = calc_lilith(jd_now)

    return {
        "pianeti_transito": transit_planets,
        "nodi_transito": nodes_now,
        "lilith_transito": lilith_now,
        "aspetti_significativi": aspects[:12],
        "data_calcolo": now.isoformat()
    }

@app.post("/solar_return")
def solar_return(data: SolarReturnRequest):
    # Trova il momento esatto del ritorno solare
    jd_natal = calc_jd(data.birth_year, data.birth_month, data.birth_day,
                       data.birth_hour, data.birth_minute)
    pos_natal_sun, _ = swe.calc_ut(jd_natal, swe.SUN)
    natal_sun_long = pos_natal_sun[0]

    # Cerca il momento del ritorno nell'anno corrente
    jd_search = calc_jd(data.current_year, data.birth_month, data.birth_day - 2, 0)
    for _ in range(10):
        pos, _ = swe.calc_ut(jd_search, swe.SUN)
        diff = (pos[0] - natal_sun_long + 360) % 360
        if diff > 180:
            diff -= 360
        if abs(diff) < 0.0001:
            break
        jd_search -= diff / 360

    # Tema della rivoluzione solare
    planets_sr = {}
    for name, pid in PLANETS.items():
        planets_sr[name] = planet_data(jd_search, pid)

    houses_sr, ascmc_sr = swe.houses(jd_search, data.latitude, data.longitude, b'P')
    asc_sign, asc_deg = deg_to_sign(ascmc_sr[0])
    mc_sign, mc_deg = deg_to_sign(ascmc_sr[1])

    houses_data = {}
    for i, cusp in enumerate(houses_sr):
        sign, deg = deg_to_sign(cusp)
        houses_data[HOUSES_LABELS[i]] = {"segno": sign, "gradi": round(deg, 2)}

    return {
        "anno": data.current_year,
        "pianeti": planets_sr,
        "case": houses_data,
        "ascendente_sr": {"segno": asc_sign, "gradi": asc_deg},
        "medio_cielo_sr": {"segno": mc_sign, "gradi": mc_deg},
        "nodi": calc_nodes(jd_search)
    }

@app.post("/compatibility")
def compatibility(data: CompatibilityRequest):
    jd1 = calc_jd(data.person1_year, data.person1_month, data.person1_day,
                  data.person1_hour, data.person1_minute)
    jd2 = calc_jd(data.person2_year, data.person2_month, data.person2_day,
                  data.person2_hour, data.person2_minute)

    planets1 = {}
    planets2 = {}
    for name, pid in PLANETS.items():
        planets1[name] = planet_data(jd1, pid)
        planets2[name] = planet_data(jd2, pid)

    houses1, ascmc1 = swe.houses(jd1, data.person1_lat, data.person1_lon, b'P')
    houses2, ascmc2 = swe.houses(jd2, data.person2_lat, data.person2_lon, b'P')

    longs1 = {name: pd['longitudine'] for name, pd in planets1.items()}
    longs2 = {name: pd['longitudine'] for name, pd in planets2.items()}

    # Sinastrìa — aspetti incrociati
    sinastria = calc_aspects(longs1, longs2)

    asc1_sign, _ = deg_to_sign(ascmc1[0])
    asc2_sign, _ = deg_to_sign(ascmc2[0])

    return {
        "persona1": {
            "pianeti": planets1,
            "ascendente": asc1_sign,
            "sole": planets1['sole']['segno'],
            "luna": planets1['luna']['segno'],
            "venere": planets1['venere']['segno'],
            "marte": planets1['marte']['segno']
        },
        "persona2": {
            "pianeti": planets2,
            "ascendente": asc2_sign,
            "sole": planets2['sole']['segno'],
            "luna": planets2['luna']['segno'],
            "venere": planets2['venere']['segno'],
            "marte": planets2['marte']['segno']
        },
        "sinastria": sinastria[:15],
        "punti_forza": [a for a in sinastria if a['aspetto'] in ['congiunzione','trigono','sestile']][:8],
        "sfide": [a for a in sinastria if a['aspetto'] in ['quadratura','opposizione']][:5]
    }
