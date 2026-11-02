#!/usr/bin/env python3
"""Projects Florida county and district boundaries to SVG paths (same format as the Texas, NC and GA files).

Usage: python3 build_shapes.py SHAPE_DIR OUT_DIR
Sources in SHAPE_DIR (U.S. Census Bureau cartographic boundary files, 500k, clipped to the shoreline):
  cb_2020_us_county_500k.zip
  cb_2018_us_cd116_500k.zip / cb_2022_us_cd118_500k.zip   congressional districts used in 2016-2020 / 2022-2024
  EOGPCRP2026.zip   the 2026 congressional plan (HB 1-D, Florida Legislature shapefile); clipped here to the state's shoreline
  cb_2018_12_sldl_500k.zip / cb_2024_...  (saved as cb_2018_sldl.zip etc.) Florida House 2012 plan (2016-2020) / 2022 plan;
  cb_2018/cb_2024 sldu: Florida Senate 2016 court-ordered plan (2016-2020) / 2022 plan
"""
import json, os, sys
import geopandas as gpd
from shapely.ops import unary_union

W = 600
CRS = '+proj=tmerc +lat_0=28 +lon_0=-83.8 +k=1 +x_0=0 +y_0=0 +datum=NAD83 +units=m'
PLANS = {'fl_ushouse_district_shapes.json': ([('c2016', 'cb_2018_us_cd116_500k.zip', 'CD116FP'), ('c2022', 'cb_2022_us_cd118_500k.zip', 'CD118FP'),
                                              ('c2026', 'EOGPCRP2026.zip', 'DISTRICT')], 1),
         'fl_house_district_shapes.json': ([('h2012', 'cb_2018_sldl.zip', 'SLDLST'), ('h2022', 'cb_2024_sldl.zip', 'SLDLST')], 0.4),
         'fl_senate_district_shapes.json': ([('s2016', 'cb_2018_sldu.zip', 'SLDUST'), ('s2022', 'cb_2024_sldu.zip', 'SLDUST')], 0.5)}
# [name, lat, lon, tier]: tier 1 always shown, tier 2 from 2x zoom, tier 3 from 4x
CITIES = [['Jacksonville', 30.3322, -81.6557, 1], ['Miami', 25.7617, -80.1918, 1], ['Tampa', 27.9506, -82.4572, 1], ['Orlando', 28.5384, -81.3789, 1],
          ['Tallahassee', 30.4383, -84.2807, 1], ['Pensacola', 30.4213, -87.2169, 1], ['Fort Myers', 26.6406, -81.8723, 1], ['Gainesville', 29.6516, -82.3248, 1],
          ['West Palm Beach', 26.7153, -80.0534, 1], ['Key West', 24.5551, -81.7800, 2],
          ['Fort Lauderdale', 26.1224, -80.1373, 2], ['St. Petersburg', 27.7676, -82.6403, 2], ['Sarasota', 27.3364, -82.5307, 2], ['Naples', 26.1420, -81.7948, 2],
          ['Lakeland', 28.0395, -81.9498, 2], ['Daytona Beach', 29.2108, -81.0228, 2], ['Ocala', 29.1872, -82.1401, 2], ['Panama City', 30.1588, -85.6602, 2],
          ['Melbourne', 28.0836, -80.6081, 2], ['Port St. Lucie', 27.2730, -80.3582, 2], ['Fort Walton Beach', 30.4058, -86.6188, 2], ['St. Augustine', 29.8946, -81.3145, 2],
          ['Sebring', 27.4956, -81.4409, 2], ['Lake City', 30.1897, -82.6393, 2], ['The Villages', 28.9342, -81.9598, 2],
          ['Hialeah', 25.8576, -80.2781, 3], ['Hollywood', 26.0112, -80.1495, 3], ['Boca Raton', 26.3683, -80.1289, 3], ['Homestead', 25.4687, -80.4776, 3],
          ['Clearwater', 27.9659, -82.8001, 3], ['Brandon', 27.9378, -82.2859, 3], ['Kissimmee', 28.2920, -81.4076, 3], ['Sanford', 28.8003, -81.2731, 3],
          ['Cape Coral', 26.5629, -81.9495, 3], ['Bradenton', 27.4989, -82.5748, 3], ['Palm Bay', 28.0345, -80.5887, 3], ['Deltona', 28.9005, -81.2637, 3],
          ['Pembroke Pines', 26.0078, -80.2963, 3], ['Coral Springs', 26.2712, -80.2706, 3], ['Port Charlotte', 26.9762, -82.0906, 3], ['Wesley Chapel', 28.2397, -82.3279, 3]]


def main(src, out):
    cty = gpd.read_file('zip://' + os.path.join(src, 'cb_2020_us_county_500k.zip'))
    cty = cty[cty.STATEFP == '12'].to_crs(CRS)
    assert len(cty) == 67
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
    json.dump(rows, open(os.path.join(out, 'fl_county_shapes.json'), 'w'), separators=(',', ':'))
    for fname, (plans, rel) in PLANS.items():
        dist = []
        for plan, f, field in plans:
            p = os.path.join(src, f)
            g = gpd.read_file('zip://' + p)
            if 'STATEFP' in g.columns:
                g = g[g.STATEFP == '12']
            g = g.to_crs(CRS)
            n = 0
            for r in g.itertuples():
                v = str(getattr(r, field)).strip()
                if not v.isdigit():
                    continue  # 'ZZZ' water areas
                geom = r.geometry.buffer(0).intersection(state) if f.startswith('EOG') else r.geometry
                dist.append({'plan': plan, 'district': int(v), 'path': path_of(geom, tol * rel)}); n += 1
            print(plan, n)
        json.dump(dist, open(os.path.join(out, fname), 'w'), separators=(',', ':'))
    import pyproj
    ll = pyproj.Transformer.from_crs('EPSG:4326', CRS, always_xy=True)
    cities = [[n, *[round(v, 1) for v in fit(*ll.transform(lo, la))], t] for n, la, lo, t in CITIES]
    json.dump({'width': W, 'height': H, 'cities': cities}, open(os.path.join(out, 'fl_map_size.json'), 'w'))
    print('viewBox', W, H)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
