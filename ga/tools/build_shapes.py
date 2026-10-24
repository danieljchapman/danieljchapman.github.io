#!/usr/bin/env python3
"""Projects Georgia county and district boundaries to SVG paths (same format as the Texas and NC files).

Usage: python3 build_shapes.py GEOJSON_DIR OUT_DIR
Sources: U.S. Census Bureau cartographic boundary files (500k), Georgia features only, saved as GeoJSON:
  shape_county.geojson    cb_2020_us_county_500k
  shape_cd115 / cd118 / cd119   congressional districts used in 2016-2020 / 2022 / 2024-2026
  shape_sldl2018 / sldl2022 / sldl2024   Georgia House districts used in 2016-2020 / 2022 / 2024-2026
  shape_sldu2018 / sldu2022 / sldu2024   Georgia Senate districts, same years
The Census files are already clipped to the shoreline. Projection: transverse Mercator centered on Georgia.
"""
import json, os, sys
from pyproj import CRS, Transformer
from shapely.geometry import shape
from shapely.ops import transform, unary_union

W = 600
PLANS = {'ga_ushouse_district_shapes.json': ([('c2012', 'cd115', 'CD115FP'), ('c2021', 'cd118', 'CD118FP'), ('c2023', 'cd119', 'CD119FP')], 1),
         'ga_house_district_shapes.json': ([('h2012', 'sldl2018', 'SLDLST'), ('h2021', 'sldl2022', 'SLDLST'), ('h2023', 'sldl2024', 'SLDLST')], 0.4),
         'ga_senate_district_shapes.json': ([('s2012', 'sldu2018', 'SLDUST'), ('s2021', 'sldu2022', 'SLDUST'), ('s2023', 'sldu2024', 'SLDUST')], 0.5)}
TARGET = CRS.from_proj4('+proj=tmerc +lat_0=32.5 +lon_0=-83.4 +k=1 +x_0=0 +y_0=0 +datum=NAD83 +units=m')
# [name, lat, lon, tier]: tier 1 always shown, tier 2 from 2x zoom, tier 3 from 4x
CITIES = [['Atlanta', 33.749, -84.388, 1], ['Savannah', 32.0809, -81.0912, 1], ['Augusta', 33.4735, -82.0105, 1], ['Columbus', 32.461, -84.9877, 1],
          ['Macon', 32.8407, -83.6324, 1], ['Athens', 33.9519, -83.3576, 1], ['Albany', 31.5785, -84.1557, 1], ['Valdosta', 30.8327, -83.2785, 1],
          ['Marietta', 33.9526, -84.5499, 2], ['Gainesville', 34.2979, -83.8241, 2], ['Warner Robins', 32.6130, -83.6242, 2], ['Rome', 34.2570, -85.1647, 2],
          ['Dalton', 34.7698, -84.9702, 2], ['Brunswick', 31.1499, -81.4915, 2], ['Statesboro', 32.4488, -81.7832, 2], ['Lawrenceville', 33.9562, -83.9880, 2],
          ['Newnan', 33.3807, -84.7997, 2], ['Tifton', 31.4505, -83.5085, 2], ['Waycross', 31.2136, -82.3540, 2], ['Thomasville', 30.8366, -83.9788, 2],
          ['Dublin', 32.5404, -82.9038, 2], ['LaGrange', 33.0393, -85.0313, 2], ['Carrollton', 33.5801, -85.0766, 2], ['Hinesville', 31.8469, -81.5959, 2],
          ['Milledgeville', 33.0801, -83.2321, 3], ['Americus', 32.0724, -84.2327, 3], ['Cartersville', 34.1651, -84.7999, 3], ['Canton', 34.2368, -84.4908, 3],
          ['Cumming', 34.2073, -84.1402, 3], ['McDonough', 33.4473, -84.1469, 3], ['Douglasville', 33.7515, -84.7477, 3], ['Alpharetta', 34.0754, -84.2941, 3],
          ['Roswell', 34.0232, -84.3616, 3], ['Sandy Springs', 33.9304, -84.3733, 3], ['Decatur', 33.7748, -84.2963, 3], ['Stone Mountain', 33.8082, -84.1702, 3],
          ['Kennesaw', 34.0234, -84.6155, 3], ['Duluth', 34.0029, -84.1446, 3], ['Smyrna', 33.8840, -84.5144, 3], ['Peachtree City', 33.3968, -84.5958, 3],
          ['Jonesboro', 33.5215, -84.3538, 3], ['Covington', 33.5968, -83.8602, 3], ['Douglas', 31.5088, -82.8499, 3], ['Moultrie', 31.1799, -83.7891, 3]]


def load(path):
    tr = Transformer.from_crs(CRS.from_epsg(4269), TARGET, always_xy=True)
    for f in json.load(open(path))['features']:
        g = shape(f['geometry'])
        if not g.is_valid:
            g = g.buffer(0)
        yield f['properties'], transform(tr.transform, g)


def path_of(geom, fit, tol):
    geom = geom.simplify(tol, preserve_topology=True)
    out = []
    polys = geom.geoms if geom.geom_type == 'MultiPolygon' else [geom] if geom.geom_type == 'Polygon' else [g for g in getattr(geom, 'geoms', []) if g.geom_type == 'Polygon']
    for p in polys:
        if p.area < (tol * 4) ** 2:
            continue
        for ring in [p.exterior] + list(p.interiors):
            pts = [fit(x, y) for x, y in ring.coords]
            out.append('M' + 'L'.join(f'{x:.1f},{y:.1f}' for x, y in pts[:-1]) + 'Z')
    return ''.join(out)


def main(src, out):
    counties = list(load(os.path.join(src, 'shape_county.geojson')))
    assert len(counties) == 159, len(counties)
    state = unary_union([g for _, g in counties])
    x0, y0, x1, y1 = state.bounds
    pad = 6
    k = (W - 2 * pad) / (x1 - x0)
    H = round((y1 - y0) * k + 2 * pad)
    fit = lambda x, y: (pad + (x - x0) * k, pad + (y1 - y) * k)
    tol = 0.5 / k
    fips = {}
    cty = []
    for rec, g in sorted(counties, key=lambda c: c[0]['NAME']):
        fips[rec['NAME']] = rec['GEOID']
        cty.append({'county_fips': rec['GEOID'], 'county': rec['NAME'], 'path': path_of(g, fit, tol)})
    json.dump(cty, open(os.path.join(out, 'ga_county_shapes.json'), 'w'), separators=(',', ':'))
    json.dump(fips, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ga_county_fips.json'), 'w'), indent=0)
    for fname, (plans, rel) in PLANS.items():
        dist = []
        for plan, key, field in plans:
            rows = list(load(os.path.join(src, f'shape_{key}.geojson')))
            for rec, g in rows:
                if not str(rec[field]).strip().isdigit():
                    continue  # 'ZZZ' water areas
                dist.append({'plan': plan, 'district': int(rec[field]), 'path': path_of(g, fit, tol * rel)})
            print(plan, len([d for d in dist if d['plan'] == plan]))
        json.dump(dist, open(os.path.join(out, fname), 'w'), separators=(',', ':'))
    ll = Transformer.from_crs(CRS.from_epsg(4326), TARGET, always_xy=True)
    cities = [[n, *[round(v, 1) for v in fit(*ll.transform(lo, la))], t] for n, la, lo, t in CITIES]
    json.dump({'width': W, 'height': H, 'cities': cities}, open(os.path.join(out, 'ga_map_size.json'), 'w'))
    print('viewBox', W, H)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
