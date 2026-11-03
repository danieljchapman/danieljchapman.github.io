#!/usr/bin/env python3
"""Projects Iowa county and district boundaries to SVG paths (same format as the other state pages).

Usage: python3 build_shapes.py SHAPE_DIR OUT_DIR
Sources in SHAPE_DIR (U.S. Census Bureau cartographic boundary files, 500k):
  cb_2020_us_county_500k.zip
  cb_2018_us_cd116_500k.zip / cb_2022_us_cd118_500k.zip   congressional districts used in 2016-2020 / 2022-2026
  cb_2018/2022_19_sldl_500k.zip and _sldu_ (saved as cb_<year>_sldl.zip / cb_<year>_sldu.zip): Iowa House and Senate, 2011 plan
      (2016-2020) / 2021 plan (2022-2026; the 2024 files are identical)
"""
import json, os, sys
import geopandas as gpd
from shapely.ops import unary_union

W = 600
CRS = '+proj=tmerc +lat_0=42 +lon_0=-93.5 +k=1 +x_0=0 +y_0=0 +datum=NAD83 +units=m'
PLANS = {'ia_ushouse_district_shapes.json': ([('c2012', 'cb_2018_us_cd116_500k.zip', 'CD116FP'), ('c2022', 'cb_2022_us_cd118_500k.zip', 'CD118FP')], 1),
         'ia_house_district_shapes.json': ([('h2012', 'cb_2018_sldl.zip', 'SLDLST'), ('h2022', 'cb_2022_sldl.zip', 'SLDLST')], 0.5),
         'ia_senate_district_shapes.json': ([('s2012', 'cb_2018_sldu.zip', 'SLDUST'), ('s2022', 'cb_2022_sldu.zip', 'SLDUST')], 0.6)}
# [name, lat, lon, tier]: tier 1 always shown, tier 2 from 2x zoom, tier 3 from 4x
CITIES = [['Des Moines', 41.5868, -93.6250, 1], ['Cedar Rapids', 41.9779, -91.6656, 1], ['Davenport', 41.5236, -90.5776, 1], ['Sioux City', 42.4999, -96.4003, 1],
          ['Iowa City', 41.6611, -91.5302, 1], ['Waterloo', 42.4928, -92.3426, 1], ['Ames', 42.0308, -93.6319, 1], ['Council Bluffs', 41.2619, -95.8608, 1],
          ['Dubuque', 42.5006, -90.6646, 1], ['Mason City', 43.1536, -93.2010, 1], ['Fort Dodge', 42.4975, -94.1680, 2], ['Ottumwa', 41.0200, -92.4113, 2],
          ['Burlington', 40.8076, -91.1129, 2], ['Marshalltown', 42.0494, -92.9080, 2], ['Muscatine', 41.4245, -91.0432, 2], ['Spencer', 43.1414, -95.1444, 2],
          ['Carroll', 42.0658, -94.8669, 2], ['Clinton', 41.8445, -90.1887, 2], ['Decorah', 43.3033, -91.7857, 2], ['Storm Lake', 42.6411, -95.2097, 2],
          ['Creston', 41.0586, -94.3614, 2], ['Le Mars', 42.7942, -96.1656, 2], ['Keokuk', 40.3973, -91.3849, 2], ['Newton', 41.6997, -93.0480, 2],
          ['Cedar Falls', 42.5349, -92.4453, 2], ['Spirit Lake', 43.4219, -95.1022, 2], ['Red Oak', 41.0097, -95.2264, 2], ['Charles City', 43.0664, -92.6724, 2],
          ['Ankeny', 41.7318, -93.6001, 3], ['West Des Moines', 41.5772, -93.7113, 3], ['Urbandale', 41.6267, -93.7122, 3], ['Waukee', 41.6117, -93.8852, 3],
          ['Johnston', 41.6730, -93.6977, 3], ['Altoona', 41.6442, -93.4647, 3], ['Indianola', 41.3580, -93.5574, 3], ['Marion', 42.0342, -91.5977, 3],
          ['Coralville', 41.6767, -91.5918, 3], ['North Liberty', 41.7492, -91.5974, 3], ['Bettendorf', 41.5245, -90.5157, 3], ['Pella', 41.4080, -92.9163, 3]]


def main(src, out):
    cty = gpd.read_file('zip://' + os.path.join(src, 'cb_2020_us_county_500k.zip'))
    cty = cty[cty.STATEFP == '19'].to_crs(CRS)
    assert len(cty) == 99
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
    json.dump(rows, open(os.path.join(out, 'ia_county_shapes.json'), 'w'), separators=(',', ':'))
    for fname, (plans, rel) in PLANS.items():
        dist = []
        for plan, f, field in plans:
            p = os.path.join(src, f)
            g = gpd.read_file('zip://' + p)
            if 'STATEFP' in g.columns:
                g = g[g.STATEFP == '19']
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
    json.dump({'width': W, 'height': H, 'cities': cities}, open(os.path.join(out, 'ia_map_size.json'), 'w'))
    print('viewBox', W, H)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
