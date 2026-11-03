#!/usr/bin/env python3
"""Projects Kansas county and district boundaries to SVG paths (same format as the other state pages).

Usage: python3 build_shapes.py SHAPE_DIR OUT_DIR
Sources in SHAPE_DIR (U.S. Census Bureau cartographic boundary files, 500k):
  cb_2020_us_county_500k.zip
  cb_2018_us_cd116_500k.zip / cb_2022_us_cd118_500k.zip   congressional districts used in 2016-2020 / 2022-2026
  cb_2018/2022_20_sldl_500k.zip and _sldu_ (saved as cb_<year>_sldl.zip / cb_<year>_sldu.zip): Kansas House and Senate, 2012 plans
      (House 2016-2020, Senate 2016-2020) / 2022 plans (House 2022-2026, Senate 2024-2026; the 2024 files are identical)
"""
import json, os, sys
import geopandas as gpd
from shapely.ops import unary_union

W = 600
CRS = '+proj=tmerc +lat_0=38.5 +lon_0=-98.4 +k=1 +x_0=0 +y_0=0 +datum=NAD83 +units=m'
PLANS = {'ks_ushouse_district_shapes.json': ([('c2012', 'cb_2018_us_cd116_500k.zip', 'CD116FP'), ('c2022', 'cb_2022_us_cd118_500k.zip', 'CD118FP')], 1),
         'ks_house_district_shapes.json': ([('h2012', 'cb_2018_sldl.zip', 'SLDLST'), ('h2022', 'cb_2022_sldl.zip', 'SLDLST')], 0.5),
         'ks_senate_district_shapes.json': ([('s2012', 'cb_2018_sldu.zip', 'SLDUST'), ('s2022', 'cb_2022_sldu.zip', 'SLDUST')], 0.6)}
# [name, lat, lon, tier]: tier 1 always shown, tier 2 from 2x zoom, tier 3 from 4x
CITIES = [['Wichita', 37.6872, -97.3301, 1], ['Kansas City', 39.1142, -94.6275, 1], ['Topeka', 39.0473, -95.6752, 1], ['Lawrence', 38.9717, -95.2353, 2],
          ['Manhattan', 39.1836, -96.5717, 2], ['Salina', 38.8403, -97.6114, 1], ['Hutchinson', 38.0608, -97.9298, 1], ['Garden City', 37.9717, -100.8727, 1],
          ['Dodge City', 37.7528, -100.0171, 1], ['Hays', 38.8792, -99.3268, 1], ['Emporia', 38.4039, -96.1817, 2], ['Pittsburg', 37.4109, -94.7050, 2],
          ['Liberal', 37.0431, -100.9210, 2], ['Junction City', 39.0286, -96.8314, 2], ['Great Bend', 38.3645, -98.7648, 2], ['Goodland', 39.3508, -101.7102, 2],
          ['Colby', 39.3958, -101.0524, 2], ['Parsons', 37.3400, -95.2611, 2], ['Independence', 37.2242, -95.7083, 2], ['Coffeyville', 37.0373, -95.6164, 2],
          ['El Dorado', 37.8172, -96.8622, 2], ['Newton', 38.0467, -97.3450, 2], ['McPherson', 38.3708, -97.6642, 2], ['Abilene', 38.9172, -97.2139, 2],
          ['Atchison', 39.5631, -95.1216, 2], ['Ottawa', 38.6156, -95.2678, 2], ['Winfield', 37.2398, -96.9956, 2], ['Leavenworth', 39.3111, -94.9225, 2],
          ['Concordia', 39.5708, -97.6625, 2], ['Pratt', 37.6439, -98.7376, 2], ['Scott City', 38.4825, -100.9071, 2], ['Chanute', 37.6792, -95.4572, 2],
          ['Overland Park', 38.9822, -94.6708, 3], ['Olathe', 38.8814, -94.8191, 3], ['Shawnee', 39.0417, -94.7202, 3], ['Lenexa', 38.9536, -94.7336, 3],
          ['Leawood', 38.9667, -94.6169, 3], ['Gardner', 38.8108, -94.9272, 3], ['Derby', 37.5456, -97.2689, 3], ['Andover', 37.7139, -97.1364, 3],
          ['Haysville', 37.5645, -97.3523, 3], ['Bel Aire', 37.7625, -97.2669, 3], ['Lansing', 39.2486, -94.9002, 3], ['Prairie Village', 38.9917, -94.6336, 3]]


def main(src, out):
    cty = gpd.read_file('zip://' + os.path.join(src, 'cb_2020_us_county_500k.zip'))
    cty = cty[cty.STATEFP == '20'].to_crs(CRS)
    assert len(cty) == 105
    state = unary_union(list(cty.geometry))
    x0, y0, x1, y1 = state.bounds
    pad = 6
    k = (W - 2 * pad) / (x1 - x0)
    H = round((y1 - y0) * k + 2 * pad)
    fit = lambda x, y: (pad + (x - x0) * k, pad + (y1 - y) * k)
    tol = 0.5 / k

    def path_of(geom, t):
        geom = geom.simplify(t, preserve_topology=True)
        polys = geom.geoms if geom.geom_type == 'MultiPolygon' else [geom] if geom.geom_type == 'Polygon' else [g for g in getattr(geom, 'geoms', []) if g.geom_type == 'Polygon']
        o = []
        for p in polys:
            if p.area < (t * 4) ** 2:
                continue
            for ring in [p.exterior] + list(p.interiors):
                pts = [fit(x, y) for x, y in ring.coords]
                o.append('M' + 'L'.join(f'{x:.1f},{y:.1f}' for x, y in pts[:-1]) + 'Z')
        return ''.join(o)

    rows = [{'county_fips': r.GEOID, 'county': r.NAME, 'path': path_of(r.geometry, tol)} for r in cty.sort_values('NAME').itertuples()]
    json.dump(rows, open(os.path.join(out, 'ks_county_shapes.json'), 'w'), separators=(',', ':'))
    for fname, (plans, rel) in PLANS.items():
        dist = []
        for plan, f, field in plans:
            p = os.path.join(src, f)
            g = gpd.read_file('zip://' + p)
            if 'STATEFP' in g.columns:
                g = g[g.STATEFP == '20']
            g = g.to_crs(CRS)
            n = 0
            for r in g.itertuples():
                v = str(getattr(r, field)).strip()
                v = v[:-2] if v.endswith('.0') else v
                if not v.isdigit():
                    continue  # 'ZZZ' water areas
                geom = r.geometry
                dist.append({'plan': plan, 'district': int(v), 'path': path_of(geom, tol * rel)}); n += 1
            print(plan, n)
        json.dump(dist, open(os.path.join(out, fname), 'w'), separators=(',', ':'))
    import pyproj
    ll = pyproj.Transformer.from_crs('EPSG:4326', CRS, always_xy=True)
    cities = [[n, *[round(v, 1) for v in fit(*ll.transform(lo, la))], t] for n, la, lo, t in CITIES]
    json.dump({'width': W, 'height': H, 'cities': cities}, open(os.path.join(out, 'ks_map_size.json'), 'w'))
    print('viewBox', W, H)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
