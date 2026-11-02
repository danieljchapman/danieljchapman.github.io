#!/usr/bin/env python3
"""Projects Michigan county and district boundaries to SVG paths (same format as the Texas, NC and GA files).

Usage: python3 build_shapes.py SHAPE_DIR OUT_DIR
Sources in SHAPE_DIR (U.S. Census Bureau cartographic boundary files, 500k, clipped to the shoreline):
  cb_2020_us_county_500k.zip
  cb_2018_us_cd116_500k.zip / cb_2022_us_cd118_500k.zip   congressional districts used in 2016-2020 / 2022-2026
  cb_2018/2022/2024_26_sldl_500k.zip (saved as cb_<year>_sldl.zip): Michigan House 2011 plan (2016-2020) / 2021 plan (2022) /
      2024 court-ordered remedial plan for Detroit-area districts (2024-2026)
  cb_2018/2022_26_sldu_500k.zip: Michigan Senate 2011 plan (2018) / 2021 plan (2022)
  CraneA1.zip (if present): the 2024 court-ordered remedial Senate plan used from 2026, clipped here to the shoreline
"""
import json, os, sys
import geopandas as gpd
from shapely.ops import unary_union

W = 600
CRS = '+proj=tmerc +lat_0=44.8 +lon_0=-86 +k=1 +x_0=0 +y_0=0 +datum=NAD83 +units=m'
PLANS = {'mi_ushouse_district_shapes.json': ([('c2012', 'cb_2018_us_cd116_500k.zip', 'CD116FP'), ('c2022', 'cb_2022_us_cd118_500k.zip', 'CD118FP')], 1),
         'mi_house_district_shapes.json': ([('h2012', 'cb_2018_sldl.zip', 'SLDLST'), ('h2022', 'cb_2022_sldl.zip', 'SLDLST'), ('h2024', 'cb_2024_sldl.zip', 'SLDLST')], 0.4),
         'mi_senate_district_shapes.json': ([('s2012', 'cb_2018_sldu.zip', 'SLDUST'), ('s2022', 'cb_2022_sldu.zip', 'SLDUST')]
                                            + ([('s2026', 'CraneA1.zip', 'DISTRICTNO')] if os.path.exists(os.path.join(sys.argv[1], 'CraneA1.zip')) else []), 0.5)}
# [name, lat, lon, tier]: tier 1 always shown, tier 2 from 2x zoom, tier 3 from 4x
CITIES = [['Detroit', 42.3314, -83.0458, 1], ['Grand Rapids', 42.9634, -85.6681, 1], ['Lansing', 42.7325, -84.5555, 1], ['Flint', 43.0125, -83.6875, 1],
          ['Ann Arbor', 42.2808, -83.7430, 2], ['Traverse City', 44.7631, -85.6206, 1], ['Marquette', 46.5436, -87.3954, 1], ['Kalamazoo', 42.2917, -85.5872, 1],
          ['Saginaw', 43.4195, -83.9508, 2], ['Sault Ste. Marie', 46.4953, -84.3453, 2], ['Muskegon', 43.2342, -86.2484, 2], ['Battle Creek', 42.3212, -85.1797, 2],
          ['Jackson', 42.2459, -84.4013, 2], ['Bay City', 43.5945, -83.8889, 2], ['Port Huron', 42.9709, -82.4249, 2], ['Alpena', 45.0617, -83.4327, 2],
          ['Escanaba', 45.7453, -87.0646, 2], ['Houghton', 47.1211, -88.5694, 2], ['Mount Pleasant', 43.5978, -84.7675, 2], ['Cadillac', 44.2519, -85.4012, 2],
          ['Petoskey', 45.3736, -84.9553, 2], ['Ironwood', 46.4547, -90.1710, 2], ['Monroe', 41.9164, -83.3977, 2], ['Benton Harbor', 42.1167, -86.4542, 2],
          ['Midland', 43.6156, -84.2472, 2], ['Gaylord', 45.0275, -84.6748, 2],
          ['Warren', 42.5145, -83.0147, 3], ['Sterling Heights', 42.5803, -83.0302, 3], ['Dearborn', 42.3223, -83.1763, 3], ['Livonia', 42.3684, -83.3527, 3],
          ['Troy', 42.6064, -83.1498, 3], ['Southfield', 42.4734, -83.2219, 3], ['Pontiac', 42.6389, -83.2910, 3], ['Novi', 42.4806, -83.4755, 3],
          ['Westland', 42.3242, -83.4002, 3], ['Royal Oak', 42.4895, -83.1446, 3], ['Ypsilanti', 42.2411, -83.6130, 3], ['East Lansing', 42.7370, -84.4839, 3],
          ['Wyoming', 42.9134, -85.7053, 3], ['Holland', 42.7875, -86.1089, 3], ['Portage', 42.2012, -85.5800, 3], ['Taylor', 42.2409, -83.2697, 3],
          ['Canton', 42.3087, -83.4822, 3], ['Clinton Twp.', 42.5868, -82.9199, 3], ['Rochester Hills', 42.6584, -83.1499, 3]]


def main(src, out):
    cty = gpd.read_file('zip://' + os.path.join(src, 'cb_2020_us_county_500k.zip'))
    cty = cty[cty.STATEFP == '26'].to_crs(CRS)
    assert len(cty) == 83
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
    json.dump(rows, open(os.path.join(out, 'mi_county_shapes.json'), 'w'), separators=(',', ':'))
    for fname, (plans, rel) in PLANS.items():
        dist = []
        for plan, f, field in plans:
            p = os.path.join(src, f)
            g = gpd.read_file('zip://' + p)
            if 'STATEFP' in g.columns:
                g = g[g.STATEFP == '26']
            g = g.to_crs(CRS)
            n = 0
            for r in g.itertuples():
                v = str(getattr(r, field)).strip()
                v = v[:-2] if v.endswith('.0') else v
                if not v.isdigit():
                    continue  # 'ZZZ' water areas
                geom = r.geometry.buffer(0).intersection(state) if f.startswith('Crane') else r.geometry
                dist.append({'plan': plan, 'district': int(v), 'path': path_of(geom, tol * rel)}); n += 1
            print(plan, n)
        json.dump(dist, open(os.path.join(out, fname), 'w'), separators=(',', ':'))
    import pyproj
    ll = pyproj.Transformer.from_crs('EPSG:4326', CRS, always_xy=True)
    cities = [[n, *[round(v, 1) for v in fit(*ll.transform(lo, la))], t] for n, la, lo, t in CITIES]
    json.dump({'width': W, 'height': H, 'cities': cities}, open(os.path.join(out, 'mi_map_size.json'), 'w'))
    print('viewBox', W, H)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
