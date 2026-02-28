from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import swisseph as swe
from datetime import datetime, timedelta
import math

app = FastAPI(title="AstroInsight Ephemeris API", version="3.0")

swe.set_ephe_path('/usr/share/ephe')

# ─── COSTANTI ────────────────────────────────────────────────────────────────

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

SIGNS_EN = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo',
            'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']

HOUSES_LABELS = ['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII']

# DIGNITÀ PLANETARIE
# domicilio, esaltazione, esilio, caduta
DIGNITIES = {
    'sole':      {'domicilio': ['Leone'], 'esaltazione': ['Ariete'], 'esilio': ['Acquario'], 'caduta': ['Bilancia']},
    'luna':      {'domicilio': ['Cancro'], 'esaltazione': ['Toro'], 'esilio': ['Capricorno'], 'caduta': ['Scorpione']},
    'mercurio':  {'domicilio': ['Gemelli','Vergine'], 'esaltazione': ['Vergine'], 'esilio': ['Sagittario','Pesci'], 'caduta': ['Pesci']},
    'venere':    {'domicilio': ['Toro','Bilancia'], 'esaltazione': ['Pesci'], 'esilio': ['Scorpione','Ariete'], 'caduta': ['Vergine']},
    'marte':     {'domicilio': ['Ariete','Scorpione'], 'esaltazione': ['Capricorno'], 'esilio': ['Bilancia','Toro'], 'caduta': ['Cancro']},
    'giove':     {'domicilio': ['Sagittario','Pesci'], 'esaltazione': ['Cancro'], 'esilio': ['Gemelli','Vergine'], 'caduta': ['Capricorno']},
    'saturno':   {'domicilio': ['Capricorno','Acquario'], 'esaltazione': ['Bilancia'], 'esilio': ['Cancro','Leone'], 'caduta': ['Ariete']},
    'urano':     {'domicilio': ['Acquario'], 'esaltazione': ['Scorpione'], 'esilio': ['Leone'], 'caduta': ['Toro']},
    'nettuno':   {'domicilio': ['Pesci'], 'esaltazione': ['Cancro'], 'esilio': ['Vergine'], 'caduta': ['Capricorno']},
    'plutone':   {'domicilio': ['Scorpione'], 'esaltazione': ['Ariete'], 'esilio': ['Toro'], 'caduta': ['Bilancia']},
    'chirone':   {'domicilio': ['Vergine'], 'esaltazione': [], 'esilio': [], 'caduta': []},
}

# ELEMENTI E QUALITÀ
ELEMENT = {'Ariete':'Fuoco','Toro':'Terra','Gemelli':'Aria','Cancro':'Acqua',
           'Leone':'Fuoco','Vergine':'Terra','Bilancia':'Aria','Scorpione':'Acqua',
           'Sagittario':'Fuoco','Capricorno':'Terra','Acquario':'Aria','Pesci':'Acqua'}

QUALITY = {'Ariete':'Cardinale','Toro':'Fisso','Gemelli':'Mutabile','Cancro':'Cardinale',
           'Leone':'Fisso','Vergine':'Mutabile','Bilancia':'Cardinale','Scorpione':'Fisso',
           'Sagittario':'Mutabile','Capricorno':'Cardinale','Acquario':'Fisso','Pesci':'Mutabile'}

# POLARITÀ
POLARITY = {'Fuoco':'Maschile','Terra':'Femminile','Aria':'Maschile','Acqua':'Femminile'}

# ─── FUNZIONI BASE ────────────────────────────────────────────────────────────

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
        "elemento": ELEMENT.get(sign, ''),
        "qualita": QUALITY.get(sign, ''),
        "retrogrado": pos[3] < 0,
        "velocita": round(pos[3], 4)
    }

def calc_lilith(jd):
    pos, _ = swe.calc_ut(jd, swe.MEAN_APOG)
    sign, deg = deg_to_sign(pos[0])
    return {"segno": sign, "gradi": deg, "longitudine": round(pos[0], 4)}

def calc_nodes(jd):
    pos_n, _ = swe.calc_ut(jd, swe.TRUE_NODE)
    sign_n, deg_n = deg_to_sign(pos_n[0])
    pos_s = (pos_n[0] + 180) % 360
    sign_s, deg_s = deg_to_sign(pos_s)
    return {
        "nodo_nord": {"segno": sign_n, "gradi": deg_n, "longitudine": round(pos_n[0], 4)},
        "nodo_sud": {"segno": sign_s, "gradi": deg_s, "longitudine": round(pos_s, 4)}
    }

def calc_aspects(planets_a, planets_b, label_a="", label_b="", orb_major=8, orb_minor=6):
    aspect_types = {
        0:   ("congiunzione", orb_major, "🔴", "neutro"),
        30:  ("semisestile", 2, "🟡", "minore"),
        45:  ("semiquadrato", 2, "🟠", "minore"),
        60:  ("sestile", orb_minor, "🟢", "armonico"),
        72:  ("quintile", 2, "🟣", "minore"),
        90:  ("quadratura", orb_major, "🔴", "tensione"),
        120: ("trigono", orb_major, "🟢", "armonico"),
        135: ("sesquiquadrato", 2, "🟠", "minore"),
        150: ("quinconce", 3, "🟡", "neutro"),
        180: ("opposizione", orb_major, "🔴", "tensione"),
    }
    aspects = []
    seen = set()
    for a_name, a_long in planets_a.items():
        for b_name, b_long in planets_b.items():
            if a_name == b_name:
                continue
            key = tuple(sorted([a_name, b_name]))
            if key in seen and label_a == label_b:
                continue
            seen.add(key)
            diff = abs(a_long - b_long) % 360
            if diff > 180:
                diff = 360 - diff
            for angle, (asp_name, orb, emoji, tipo) in aspect_types.items():
                if abs(diff - angle) <= orb:
                    aspects.append({
                        "pianeta_a": f"{label_a}{a_name}" if label_a else a_name,
                        "pianeta_b": f"{label_b}{b_name}" if label_b else b_name,
                        "aspetto": asp_name,
                        "emoji": emoji,
                        "tipo": tipo,
                        "angolo_esatto": angle,
                        "orb": round(abs(diff - angle), 2),
                        "applicante": diff < angle
                    })
    aspects.sort(key=lambda x: x["orb"])
    return aspects

def calc_dignity(planet_name, sign):
    if planet_name not in DIGNITIES:
        return "neutro"
    d = DIGNITIES[planet_name]
    if sign in d['domicilio']:
        return "domicilio"
    if sign in d['esaltazione']:
        return "esaltazione"
    if sign in d['esilio']:
        return "esilio"
    if sign in d['caduta']:
        return "caduta"
    return "neutro"

def calc_planet_in_house(planet_long, houses):
    for i in range(12):
        h_start = houses[i]
        h_end = houses[(i + 1) % 12]
        if h_end < h_start:
            h_end += 360
        p = planet_long if planet_long >= h_start else planet_long + 360
        if h_start <= p < h_end:
            return HOUSES_LABELS[i]
    return "I"

# ─── PATTERN ASTROLOGICI ─────────────────────────────────────────────────────

def detect_patterns(longs_map):
    patterns = []
    names = list(longs_map.keys())
    longs = list(longs_map.values())

    # Grand Trine — tre pianeti a ~120° l'uno dall'altro
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            for k in range(j+1, len(names)):
                d1 = abs(longs[i]-longs[j])%360; d1=min(d1,360-d1)
                d2 = abs(longs[j]-longs[k])%360; d2=min(d2,360-d2)
                d3 = abs(longs[i]-longs[k])%360; d3=min(d3,360-d3)
                if all(abs(d-120)<=8 for d in [d1,d2,d3]):
                    elem = ELEMENT.get(deg_to_sign(longs[i])[0],'')
                    patterns.append({
                        "nome": "Gran Trigono",
                        "emoji": "🔺",
                        "pianeti": [names[i], names[j], names[k]],
                        "elemento": elem,
                        "descrizione": f"Gran trigono in {elem} — grande armonia e talento naturale"
                    })

    # T-Square — due pianeti in opposizione + uno in quadratura ad entrambi
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            d_opp = abs(longs[i]-longs[j])%360; d_opp=min(d_opp,360-d_opp)
            if abs(d_opp-180)<=8:
                for k in range(len(names)):
                    if k==i or k==j: continue
                    d1=abs(longs[k]-longs[i])%360; d1=min(d1,360-d1)
                    d2=abs(longs[k]-longs[j])%360; d2=min(d2,360-d2)
                    if abs(d1-90)<=8 and abs(d2-90)<=8:
                        patterns.append({
                            "nome": "T-Quadrato",
                            "emoji": "⚡",
                            "pianeti": [names[i], names[j], names[k]],
                            "vertice": names[k],
                            "descrizione": f"T-quadrato con vertice in {names[k]} — tensione e drive verso la crescita"
                        })

    # Grand Cross — quattro pianeti, due opposizioni incrociate
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            d1=abs(longs[i]-longs[j])%360; d1=min(d1,360-d1)
            if abs(d1-180)<=8:
                for k in range(j+1, len(names)):
                    for l in range(k+1, len(names)):
                        d2=abs(longs[k]-longs[l])%360; d2=min(d2,360-d2)
                        if abs(d2-180)<=8:
                            d3=abs(longs[i]-longs[k])%360; d3=min(d3,360-d3)
                            if abs(d3-90)<=8:
                                patterns.append({
                                    "nome": "Croce Cardinale",
                                    "emoji": "✚",
                                    "pianeti": [names[i], names[j], names[k], names[l]],
                                    "descrizione": "Grande croce — sfide intense ma forza eccezionale"
                                })

    # Yod — due pianeti in sestile, entrambi in quinconce con un terzo
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            d_sest=abs(longs[i]-longs[j])%360; d_sest=min(d_sest,360-d_sest)
            if abs(d_sest-60)<=6:
                for k in range(len(names)):
                    if k==i or k==j: continue
                    d1=abs(longs[k]-longs[i])%360; d1=min(d1,360-d1)
                    d2=abs(longs[k]-longs[j])%360; d2=min(d2,360-d2)
                    if abs(d1-150)<=3 and abs(d2-150)<=3:
                        patterns.append({
                            "nome": "Yod (Dito di Dio)",
                            "emoji": "☝️",
                            "pianeti": [names[i], names[j], names[k]],
                            "vertice": names[k],
                            "descrizione": f"Yod con vertice in {names[k]} — missione karmica speciale"
                        })

    # Stellium — 3+ pianeti nello stesso segno
    sign_groups = {}
    for name, long in longs_map.items():
        sign = deg_to_sign(long)[0]
        sign_groups.setdefault(sign, []).append(name)
    for sign, planets in sign_groups.items():
        if len(planets) >= 3:
            patterns.append({
                "nome": f"Stellium in {sign}",
                "emoji": "⭐",
                "pianeti": planets,
                "descrizione": f"Concentrazione di energia in {sign} — focus e intensità su queste tematiche"
            })

    return patterns

# ─── PARTI ARABE ─────────────────────────────────────────────────────────────

def calc_arabic_parts(asc, sun, moon, mars, saturn, jupiter, mercury, venus, planets_map):
    parts = {}
    def part(formula):
        return round(formula % 360, 4)

    parts['fortuna'] = {
        "longitudine": part(asc + moon - sun),
        "nome": "Parte della Fortuna",
        "descrizione": "Felicità materiale e fisica"
    }
    parts['spirito'] = {
        "longitudine": part(asc + sun - moon),
        "nome": "Parte dello Spirito",
        "descrizione": "Vita spirituale e mentale"
    }
    parts['amore'] = {
        "longitudine": part(asc + venus - sun),
        "nome": "Parte dell'Amore",
        "descrizione": "Relazioni romantiche"
    }
    parts['matrimonio_m'] = {
        "longitudine": part(asc + venus - saturn),
        "nome": "Parte del Matrimonio (M)",
        "descrizione": "Unione e partnership"
    }
    parts['lavoro'] = {
        "longitudine": part(asc + mars - saturn),
        "nome": "Parte della Carriera",
        "descrizione": "Vocazione professionale"
    }
    parts['salute'] = {
        "longitudine": part(asc + mars - moon),
        "nome": "Parte della Salute",
        "descrizione": "Vitalità e benessere fisico"
    }
    parts['denaro'] = {
        "longitudine": part(asc + jupiter - sun),
        "nome": "Parte della Ricchezza",
        "descrizione": "Abbondanza materiale"
    }
    parts['viaggi'] = {
        "longitudine": part(asc + saturn - sun),
        "nome": "Parte dei Viaggi",
        "descrizione": "Spostamenti e cambiamenti"
    }
    parts['figli'] = {
        "longitudine": part(asc + jupiter - moon),
        "nome": "Parte dei Figli",
        "descrizione": "Fertilità e creatività"
    }
    parts['intelligenza'] = {
        "longitudine": part(asc + mercury - sun),
        "nome": "Parte dell'Intelligenza",
        "descrizione": "Mente e comunicazione"
    }

    # Aggiungi segno e gradi a ogni parte
    for k, v in parts.items():
        sign, deg = deg_to_sign(v['longitudine'])
        v['segno'] = sign
        v['gradi'] = deg
        v['elemento'] = ELEMENT.get(sign, '')

    return parts

# ─── PROGRESSIONI SECONDARIE ─────────────────────────────────────────────────

def calc_secondary_progressions(birth_jd, age_years):
    # Un giorno = un anno (progressioni secondarie)
    progressed_jd = birth_jd + age_years
    planets_prog = {}
    for name, pid in PLANETS.items():
        planets_prog[name] = planet_data(progressed_jd, pid)
    return planets_prog

# ─── DISTRIBUZIONE ELEMENTI/QUALITÀ ──────────────────────────────────────────

def calc_distribution(planets_data):
    elements = {'Fuoco': [], 'Terra': [], 'Aria': [], 'Acqua': []}
    qualities = {'Cardinale': [], 'Fisso': [], 'Mutabile': []}
    polarities = {'Maschile': [], 'Femminile': []}

    for name, pd in planets_data.items():
        sign = pd['segno']
        el = ELEMENT.get(sign, '')
        qu = QUALITY.get(sign, '')
        po = POLARITY.get(el, '')
        if el: elements[el].append(name)
        if qu: qualities[qu].append(name)
        if po: polarities[po].append(name)

    dominant_element = max(elements, key=lambda k: len(elements[k]))
    dominant_quality = max(qualities, key=lambda k: len(qualities[k]))

    return {
        "elementi": {k: {"pianeti": v, "count": len(v)} for k, v in elements.items()},
        "qualita": {k: {"pianeti": v, "count": len(v)} for k, v in qualities.items()},
        "polarita": {k: {"pianeti": v, "count": len(v)} for k, v in polarities.items()},
        "elemento_dominante": dominant_element,
        "qualita_dominante": dominant_quality,
    }

# ─── CARTA COMPOSITA ─────────────────────────────────────────────────────────

def calc_composite(planets1, planets2, asc1, asc2):
    composite = {}
    for name in planets1:
        l1 = planets1[name]['longitudine']
        l2 = planets2[name]['longitudine']
        # Metodo del punto medio
        diff = abs(l1 - l2)
        if diff > 180:
            mid = ((l1 + l2 + 360) / 2) % 360
        else:
            mid = (l1 + l2) / 2
        sign, deg = deg_to_sign(mid)
        composite[name] = {
            "longitudine": round(mid, 4),
            "segno": sign,
            "gradi": deg,
            "elemento": ELEMENT.get(sign, ''),
            "qualita": QUALITY.get(sign, '')
        }
    # Ascendente composito
    diff_asc = abs(asc1 - asc2)
    if diff_asc > 180:
        mid_asc = ((asc1 + asc2 + 360) / 2) % 360
    else:
        mid_asc = (asc1 + asc2) / 2
    asc_sign, asc_deg = deg_to_sign(mid_asc)
    composite['ascendente'] = {"segno": asc_sign, "gradi": asc_deg, "longitudine": round(mid_asc, 4)}
    return composite

# ─── MODELS ──────────────────────────────────────────────────────────────────

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

class ProgressionRequest(BaseModel):
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int = 12
    birth_minute: int = 0
    age_years: int

# ─── ENDPOINTS ───────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "AstroInsight Ephemeris API",
        "status": "active",
        "version": "3.0",
        "endpoints": ["/today", "/natal", "/transits", "/solar_return",
                      "/compatibility", "/progressions", "/lunar_phases", "/ephemeris"]
    }

@app.get("/today")
def today_planets():
    now = datetime.utcnow()
    jd = calc_jd(now.year, now.month, now.day, now.hour, now.minute)
    planets_data = {}
    for name, pid in PLANETS.items():
        planets_data[name] = planet_data(jd, pid)
    nodes = calc_nodes(jd)
    lilith = calc_lilith(jd)
    patterns = detect_patterns({n: p['longitudine'] for n, p in planets_data.items()})
    distribution = calc_distribution(planets_data)

    # Luna fase
    sun_long = planets_data['sole']['longitudine']
    moon_long = planets_data['luna']['longitudine']
    moon_phase_deg = (moon_long - sun_long) % 360
    if moon_phase_deg < 45: phase = "Luna Nuova"
    elif moon_phase_deg < 90: phase = "Luna Crescente"
    elif moon_phase_deg < 135: phase = "Primo Quarto"
    elif moon_phase_deg < 180: phase = "Gibbosa Crescente"
    elif moon_phase_deg < 225: phase = "Luna Piena"
    elif moon_phase_deg < 270: phase = "Gibbosa Calante"
    elif moon_phase_deg < 315: phase = "Ultimo Quarto"
    else: phase = "Luna Calante"

    return {
        "data": now.strftime("%d/%m/%Y"),
        "ora_utc": now.strftime("%H:%M"),
        "pianeti": planets_data,
        "nodi_lunari": nodes,
        "lilith": lilith,
        "fase_lunare": phase,
        "angolo_lunare": round(moon_phase_deg, 2),
        "pattern": patterns,
        "distribuzione": distribution
    }

@app.post("/natal")
def natal_chart(data: BirthData):
    jd = calc_jd(data.year, data.month, data.day, data.hour, data.minute)

    # Pianeti con dignità e casa
    houses_raw, ascmc = swe.houses(jd, data.latitude, data.longitude, b'P')
    asc_long = ascmc[0]
    mc_long = ascmc[1]
    dsc_long = (asc_long + 180) % 360
    ic_long = (mc_long + 180) % 360

    planets_data = {}
    for name, pid in PLANETS.items():
        pd = planet_data(jd, pid)
        pd['dignita'] = calc_dignity(name, pd['segno'])
        pd['casa'] = calc_planet_in_house(pd['longitudine'], list(houses_raw))
        planets_data[name] = pd

    nodes = calc_nodes(jd)
    lilith = calc_lilith(jd)

    # Case
    asc_sign, asc_deg = deg_to_sign(asc_long)
    mc_sign, mc_deg = deg_to_sign(mc_long)
    dsc_sign, dsc_deg = deg_to_sign(dsc_long)
    ic_sign, ic_deg = deg_to_sign(ic_long)

    houses_data = {}
    for i, cusp in enumerate(houses_raw):
        sign, deg = deg_to_sign(cusp)
        houses_data[HOUSES_LABELS[i]] = {
            "segno": sign, "gradi": round(deg, 2),
            "longitudine": round(cusp, 4),
            "elemento": ELEMENT.get(sign, ''),
            "qualita": QUALITY.get(sign, '')
        }

    # Parti arabe
    p = planets_data
    arabic = calc_arabic_parts(
        asc_long,
        p['sole']['longitudine'], p['luna']['longitudine'],
        p['marte']['longitudine'], p['saturno']['longitudine'],
        p['giove']['longitudine'], p['mercurio']['longitudine'],
        p['venere']['longitudine'], {n: pd['longitudine'] for n, pd in p.items()}
    )

    # Aspetti
    long_map = {name: pd['longitudine'] for name, pd in planets_data.items()}
    # Aggiungi angoli
    long_map['ascendente'] = asc_long
    long_map['medio_cielo'] = mc_long
    aspects = calc_aspects(long_map, long_map)

    # Pattern
    patterns = detect_patterns({n: pd['longitudine'] for n, pd in planets_data.items()})

    # Distribuzione
    distribution = calc_distribution(planets_data)

    # Fase lunare alla nascita
    sun_long = planets_data['sole']['longitudine']
    moon_long = planets_data['luna']['longitudine']
    moon_phase_deg = (moon_long - sun_long) % 360
    if moon_phase_deg < 45: phase = "Luna Nuova"
    elif moon_phase_deg < 90: phase = "Luna Crescente"
    elif moon_phase_deg < 135: phase = "Primo Quarto"
    elif moon_phase_deg < 180: phase = "Gibbosa Crescente"
    elif moon_phase_deg < 225: phase = "Luna Piena"
    elif moon_phase_deg < 270: phase = "Gibbosa Calante"
    elif moon_phase_deg < 315: phase = "Ultimo Quarto"
    else: phase = "Luna Calante"

    # Dominante astrologico (pianeta che governa il segno con più punti pesanti)
    dominant_score = {}
    weights = {'sole': 5, 'luna': 4, 'ascendente': 4, 'mercurio': 2,
               'venere': 2, 'marte': 2, 'giove': 2, 'saturno': 2,
               'urano': 1, 'nettuno': 1, 'plutone': 1, 'chirone': 1}
    rulers = {
        'Ariete': 'marte', 'Toro': 'venere', 'Gemelli': 'mercurio', 'Cancro': 'luna',
        'Leone': 'sole', 'Vergine': 'mercurio', 'Bilancia': 'venere', 'Scorpione': 'plutone',
        'Sagittario': 'giove', 'Capricorno': 'saturno', 'Acquario': 'urano', 'Pesci': 'nettuno'
    }
    for name, pd in planets_data.items():
        ruler = rulers.get(pd['segno'], '')
        if ruler:
            dominant_score[ruler] = dominant_score.get(ruler, 0) + weights.get(name, 1)
    # Aggiungi ascendente
    asc_ruler = rulers.get(asc_sign, '')
    if asc_ruler:
        dominant_score[asc_ruler] = dominant_score.get(asc_ruler, 0) + 4

    dominant_planet = max(dominant_score, key=dominant_score.get) if dominant_score else 'sole'

    return {
        "dati_nascita": {
            "anno": data.year, "mese": data.month, "giorno": data.day,
            "ora": data.hour, "minuto": data.minute,
            "latitudine": data.latitude, "longitudine": data.longitude
        },
        "pianeti": planets_data,
        "angoli": {
            "ascendente": {"segno": asc_sign, "gradi": asc_deg, "longitudine": round(asc_long, 4)},
            "discendente": {"segno": dsc_sign, "gradi": dsc_deg, "longitudine": round(dsc_long, 4)},
            "medio_cielo": {"segno": mc_sign, "gradi": mc_deg, "longitudine": round(mc_long, 4)},
            "fondo_cielo": {"segno": ic_sign, "gradi": ic_deg, "longitudine": round(ic_long, 4)},
        },
        "case": houses_data,
        "nodi_lunari": nodes,
        "lilith": lilith,
        "parti_arabe": arabic,
        "aspetti": aspects[:25],
        "pattern": patterns,
        "distribuzione": distribution,
        "fase_lunare_nascita": {"fase": phase, "angolo": round(moon_phase_deg, 2)},
        "pianeta_dominante": dominant_planet,
        "julian_day": jd
    }

@app.post("/transits")
def current_transits(data: TransitRequest):
    now = datetime.utcnow()
    jd_now = calc_jd(now.year, now.month, now.day, now.hour, now.minute)
    jd_natal = calc_jd(data.birth_year, data.birth_month, data.birth_day,
                       data.birth_hour, data.birth_minute)

    natal_planets = {}
    transit_planets = {}
    for name, pid in PLANETS.items():
        pos_n, _ = swe.calc_ut(jd_natal, pid)
        natal_planets[name] = pos_n[0]
        transit_planets[name] = planet_data(jd_now, pid)

    nodes_natal = calc_nodes(jd_natal)
    natal_planets['nodo_nord'] = nodes_natal['nodo_nord']['longitudine']

    houses_natal, ascmc_natal = swe.houses(jd_natal, data.latitude, data.longitude, b'P')
    natal_planets['ascendente'] = ascmc_natal[0]
    natal_planets['medio_cielo'] = ascmc_natal[1]

    transit_longs = {name: pd['longitudine'] for name, pd in transit_planets.items()}
    aspects = calc_aspects(transit_longs, natal_planets, "T:", "N:")

    nodes_now = calc_nodes(jd_now)
    lilith_now = calc_lilith(jd_now)

    # Fase lunare attuale
    sun_now = transit_planets['sole']['longitudine']
    moon_now = transit_planets['luna']['longitudine']
    phase_deg = (moon_now - sun_now) % 360
    if phase_deg < 45: phase = "Luna Nuova"
    elif phase_deg < 90: phase = "Luna Crescente"
    elif phase_deg < 135: phase = "Primo Quarto"
    elif phase_deg < 180: phase = "Gibbosa Crescente"
    elif phase_deg < 225: phase = "Luna Piena"
    elif phase_deg < 270: phase = "Gibbosa Calante"
    elif phase_deg < 315: phase = "Ultimo Quarto"
    else: phase = "Luna Calante"

    return {
        "data_calcolo": now.strftime("%d/%m/%Y %H:%M UTC"),
        "pianeti_transito": transit_planets,
        "nodi_transito": nodes_now,
        "lilith_transito": lilith_now,
        "fase_lunare": phase,
        "aspetti_significativi": aspects[:15],
        "aspetti_armonici": [a for a in aspects if a['tipo']=='armonico'][:8],
        "aspetti_tensione": [a for a in aspects if a['tipo']=='tensione'][:8],
    }

@app.post("/solar_return")
def solar_return(data: SolarReturnRequest):
    jd_natal = calc_jd(data.birth_year, data.birth_month, data.birth_day,
                       data.birth_hour, data.birth_minute)
    pos_natal_sun, _ = swe.calc_ut(jd_natal, swe.SUN)
    natal_sun_long = pos_natal_sun[0]

    jd_search = calc_jd(data.current_year, data.birth_month, max(data.birth_day-2, 1), 0)
    for _ in range(15):
        pos, _ = swe.calc_ut(jd_search, swe.SUN)
        diff = (pos[0] - natal_sun_long + 360) % 360
        if diff > 180: diff -= 360
        if abs(diff) < 0.0001: break
        jd_search -= diff / 360

    planets_sr = {}
    for name, pid in PLANETS.items():
        pd = planet_data(jd_search, pid)
        pd['dignita'] = calc_dignity(name, pd['segno'])
        planets_sr[name] = pd

    houses_sr, ascmc_sr = swe.houses(jd_search, data.latitude, data.longitude, b'P')
    asc_sign, asc_deg = deg_to_sign(ascmc_sr[0])
    mc_sign, mc_deg = deg_to_sign(ascmc_sr[1])

    houses_data = {}
    for i, cusp in enumerate(houses_sr):
        sign, deg = deg_to_sign(cusp)
        houses_data[HOUSES_LABELS[i]] = {"segno": sign, "gradi": round(deg, 2)}

    longs = {n: pd['longitudine'] for n, pd in planets_sr.items()}
    aspects = calc_aspects(longs, longs)
    patterns = detect_patterns(longs)
    distribution = calc_distribution(planets_sr)

    return {
        "anno": data.current_year,
        "momento_esatto_jd": round(jd_search, 4),
        "pianeti": planets_sr,
        "case": houses_data,
        "angoli": {
            "ascendente": {"segno": asc_sign, "gradi": asc_deg},
            "medio_cielo": {"segno": mc_sign, "gradi": mc_deg}
        },
        "nodi": calc_nodes(jd_search),
        "aspetti": aspects[:15],
        "pattern": patterns,
        "distribuzione": distribution
    }

@app.post("/compatibility")
def compatibility(data: CompatibilityRequest):
    jd1 = calc_jd(data.person1_year, data.person1_month, data.person1_day,
                  data.person1_hour, data.person1_minute)
    jd2 = calc_jd(data.person2_year, data.person2_month, data.person2_day,
                  data.person2_hour, data.person2_minute)

    planets1, planets2 = {}, {}
    for name, pid in PLANETS.items():
        pd1 = planet_data(jd1, pid)
        pd1['dignita'] = calc_dignity(name, pd1['segno'])
        planets1[name] = pd1
        pd2 = planet_data(jd2, pid)
        pd2['dignita'] = calc_dignity(name, pd2['segno'])
        planets2[name] = pd2

    houses1, ascmc1 = swe.houses(jd1, data.person1_lat, data.person1_lon, b'P')
    houses2, ascmc2 = swe.houses(jd2, data.person2_lat, data.person2_lon, b'P')

    asc1_sign, asc1_deg = deg_to_sign(ascmc1[0])
    asc2_sign, asc2_deg = deg_to_sign(ascmc2[0])
    mc1_sign, mc1_deg = deg_to_sign(ascmc1[1])
    mc2_sign, mc2_deg = deg_to_sign(ascmc2[1])

    longs1 = {n: pd['longitudine'] for n, pd in planets1.items()}
    longs2 = {n: pd['longitudine'] for n, pd in planets2.items()}
    longs1['ascendente'] = ascmc1[0]
    longs2['ascendente'] = ascmc2[0]

    # Sinastrìa
    sinastria = calc_aspects(longs1, longs2, "P1:", "P2:")

    # Carta composita
    composita = calc_composite(planets1, planets2, ascmc1[0], ascmc2[0])
    comp_longs = {n: v['longitudine'] for n, v in composita.items() if 'longitudine' in v}
    composita_aspects = calc_aspects(comp_longs, comp_longs)
    composita_patterns = detect_patterns({n: v['longitudine'] for n, v in composita.items() if n != 'ascendente' and 'longitudine' in v})

    # Score compatibilità
    score = 0
    for a in sinastria:
        if a['tipo'] == 'armonico': score += max(0, 8 - a['orb'])
        elif a['tipo'] == 'tensione': score -= max(0, 4 - a['orb'])
    compat_pct = min(100, max(0, int(50 + score * 2)))

    # Distribuzione per entrambi
    dist1 = calc_distribution(planets1)
    dist2 = calc_distribution(planets2)

    return {
        "persona1": {
            "pianeti": planets1,
            "ascendente": {"segno": asc1_sign, "gradi": asc1_deg},
            "medio_cielo": {"segno": mc1_sign, "gradi": mc1_deg},
            "distribuzione": dist1,
            "sole": planets1['sole']['segno'],
            "luna": planets1['luna']['segno'],
            "venere": planets1['venere']['segno'],
            "marte": planets1['marte']['segno'],
        },
        "persona2": {
            "pianeti": planets2,
            "ascendente": {"segno": asc2_sign, "gradi": asc2_deg},
            "medio_cielo": {"segno": mc2_sign, "gradi": mc2_deg},
            "distribuzione": dist2,
            "sole": planets2['sole']['segno'],
            "luna": planets2['luna']['segno'],
            "venere": planets2['venere']['segno'],
            "marte": planets2['marte']['segno'],
        },
        "sinastria": {
            "tutti": sinastria[:20],
            "armonici": [a for a in sinastria if a['tipo']=='armonico'][:10],
            "tensione": [a for a in sinastria if a['tipo']=='tensione'][:8],
        },
        "carta_composita": {
            "pianeti": composita,
            "aspetti": composita_aspects[:12],
            "pattern": composita_patterns,
        },
        "compatibilita_percentuale": compat_pct,
        "nodi1": calc_nodes(jd1),
        "nodi2": calc_nodes(jd2),
    }

@app.post("/progressions")
def secondary_progressions(data: ProgressionRequest):
    jd_natal = calc_jd(data.birth_year, data.birth_month, data.birth_day,
                       data.birth_hour, data.birth_minute)
    prog_planets = calc_secondary_progressions(jd_natal, data.age_years)

    # Confronta con natale
    natal_planets = {}
    for name, pid in PLANETS.items():
        natal_planets[name] = planet_data(jd_natal, pid)

    prog_longs = {n: pd['longitudine'] for n, pd in prog_planets.items()}
    natal_longs = {n: pd['longitudine'] for n, pd in natal_planets.items()}
    aspects = calc_aspects(prog_longs, natal_longs, "P:", "N:")

    return {
        "eta": data.age_years,
        "pianeti_progressati": prog_planets,
        "pianeti_natali": natal_planets,
        "aspetti_progressati": aspects[:15],
        "sole_progressato": prog_planets.get('sole', {}),
        "luna_progressata": prog_planets.get('luna', {}),
    }

@app.get("/lunar_phases")
def lunar_phases():
    """Prossime 4 fasi lunari"""
    now = datetime.utcnow()
    jd_now = calc_jd(now.year, now.month, now.day, now.hour, now.minute)
    phases = []
    jd = jd_now
    found = 0
    while found < 8:
        sun_pos, _ = swe.calc_ut(jd, swe.SUN)
        moon_pos, _ = swe.calc_ut(jd, swe.MOON)
        angle = (moon_pos[0] - sun_pos[0]) % 360
        for target, name in [(0,"Luna Nuova 🌑"),(90,"Primo Quarto 🌓"),(180,"Luna Piena 🌕"),(270,"Ultimo Quarto 🌗")]:
            diff = (angle - target) % 360
            if diff < 1 or diff > 359:
                dt = datetime(1858, 11, 17) + timedelta(days=jd - 2400000.5)
                phases.append({"nome": name, "data": dt.strftime("%d/%m/%Y"), "jd": round(jd, 2)})
                found += 1
        jd += 0.5
    return {"fasi": phases[:8]}

@app.post("/ephemeris")
def ephemeris_range(data: BirthData):
    """Posizioni planetarie per 7 giorni da una data"""
    jd_start = calc_jd(data.year, data.month, data.day)
    result = []
    for i in range(7):
        jd = jd_start + i
        day_data = {}
        for name, pid in PLANETS.items():
            pd = planet_data(jd, pid)
            day_data[name] = {"segno": pd['segno'], "gradi": pd['gradi'], "retrogrado": pd['retrogrado']}
        dt = datetime(1858, 11, 17) + timedelta(days=jd - 2400000.5)
        result.append({"data": dt.strftime("%d/%m/%Y"), "pianeti": day_data})
    return {"efemeridi": result}
