#!/usr/bin/env python3
"""Projects Arizona county and district boundaries to SVG paths (same format as the Texas, NC and GA files).

Usage: python3 build_shapes.py SHAPE_DIR OUT_DIR
Sources in SHAPE_DIR (U.S. Census Bureau cartographic boundary files, 500k, clipped to the shoreline):
  cb_2020_us_county_500k.zip
  cb_2018/2022_04_sldu_500k.zip   legislative districts (one map for both chambers): 2011 commission plan (2012-2020), 2021 commission plan (2022-2026)
  cb_2018_us_cd116 / cb_2022_us_cd118_500k.zip   congressional districts: 2011 plan (2012-2020), 2021 plan (2022-2026)
"""
import json, os, sys
import geopandas as gpd
from shapely.ops import unary_union

W = 600
CRS = '+proj=tmerc +lat_0=34.2 +lon_0=-111.7 +k=1 +x_0=0 +y_0=0 +datum=NAD83 +units=m'
PLANS = {'az_house_district_shapes.json': ([('l2012', 'cb_2018_04_sldu_500k.zip', 'SLDUST'), ('l2022', 'cb_2022_04_sldu_500k.zip', 'SLDUST')], 0.4),
         'az_senate_district_shapes.json': ([('l2012', 'cb_2018_04_sldu_500k.zip', 'SLDUST'), ('l2022', 'cb_2022_04_sldu_500k.zip', 'SLDUST')], 0.4),
         'az_ushouse_district_shapes.json': ([('c2012', 'cb_2018_us_cd116_500k.zip', 'CD116FP'), ('c2022', 'cb_2022_us_cd118_500k.zip', 'CD118FP')], 0.5)}
# [name, lat, lon, tier]: tier 1 always shown, tier 2 from 2x zoom, tier 3 from 4x
CITIES = [['Phoenix', 33.4484, -112.0740, 1], ['Tucson', 32.2226, -110.9747, 1], ['Flagstaff', 35.1983, -111.6513, 1], ['Yuma', 32.6927, -114.6277, 1],
          ['Prescott', 34.5400, -112.4685, 1], ['Lake Havasu City', 34.4839, -114.3225, 1], ['Sierra Vista', 31.5455, -110.2773, 1], ['Show Low', 34.2542, -110.0298, 1],
          ['Kingman', 35.1894, -114.0530, 2], ['Casa Grande', 32.8795, -111.7574, 2], ['Payson', 34.2309, -111.3251, 2], ['Nogales', 31.3404, -110.9343, 2],
          ['Bullhead City', 35.1478, -114.5683, 2], ['Douglas', 31.3445, -109.5453, 2], ['Globe', 33.3942, -110.7865, 2], ['Safford', 32.8340, -109.7076, 2],
          ['Page', 36.9147, -111.4558, 2], ['Window Rock', 35.6803, -109.0526, 2], ['Winslow', 35.0242, -110.6974, 2], ['Cottonwood', 34.7392, -112.0099, 2],
          ['Maricopa', 33.0581, -112.0476, 2], ['Mesa', 33.4152, -111.8315, 2], ['Glendale', 33.5387, -112.1860, 3], ['Scottsdale', 33.4942, -111.9261, 3],
          ['Chandler', 33.3062, -111.8413, 3], ['Gilbert', 33.3528, -111.7890, 3], ['Tempe', 33.4255, -111.9400, 3], ['Peoria', 33.5806, -112.2374, 3],
          ['Surprise', 33.6292, -112.3680, 3], ['Goodyear', 33.4353, -112.3577, 3], ['Buckeye', 33.3703, -112.5838, 3], ['Queen Creek', 33.2487, -111.6343, 3],
          ['Marana', 32.4367, -111.2254, 3], ['Oro Valley', 32.3909, -110.9665, 3], ['Sahuarita', 31.9576, -110.9556, 3], ['San Tan Valley', 33.1911, -111.5282, 3],
          ['Apache Junction', 33.4151, -111.5496, 3], ['Fountain Hills', 33.6117, -111.7174, 3], ['Avondale', 33.4356, -112.3496, 3]]


def main(src, out):
    cty = gpd.read_file('zip://' + os.path.join(src, 'cb_2020_us_county_500k.zip'))
    cty = cty[cty.STATEFP == '04'].to_crs(CRS)
    assert len(cty) == 15
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
    json.dump(rows, open(os.path.join(out, 'az_county_shapes.json'), 'w'), separators=(',', ':'))
    for fname, (plans, rel) in PLANS.items():
        dist = []
        for plan, f, field in plans:
            p = os.path.join(src, f)
            g = gpd.read_file(p if f.endswith('.geojson') else 'zip://' + p)
            if 'STATEFP' in g.columns:
                g = g[g.STATEFP == '04']
            g = g.to_crs(CRS)
            n = 0
            for r in g.itertuples():
                v = str(getattr(r, field)).strip()
                if not v.isdigit():
                    continue  # 'ZZZ' water areas
                geom = r.geometry.buffer(0).intersection(state) if f.endswith('.geojson') else r.geometry
                dist.append({'plan': plan, 'district': int(v), 'path': path_of(geom, tol * rel)}); n += 1
            print(plan, n)
        json.dump(dist, open(os.path.join(out, fname), 'w'), separators=(',', ':'))
    import pyproj
    ll = pyproj.Transformer.from_crs('EPSG:4326', CRS, always_xy=True)
    cities = [[n, *[round(v, 1) for v in fit(*ll.transform(lo, la))], t] for n, la, lo, t in CITIES]
    json.dump({'width': W, 'height': H, 'cities': cities}, open(os.path.join(out, 'az_map_size.json'), 'w'))
    print('viewBox', W, H)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
